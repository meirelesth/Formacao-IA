<?php
declare(strict_types=1);

/** Hosted PagBank checkout: card data never passes through this application. */
final class Payments {
    public const PRODUCTS = [
        'basica'=>['name'=>'Formação Básica em IA','amount'=>99700,'hours'=>10,'modules'=>8],
        'avancada'=>['name'=>'Formação Avançada em IA','amount'=>169900,'hours'=>20,'modules'=>10],
    ];
    public const SCHEMA = "CREATE TABLE IF NOT EXISTS payment_orders (
        reference_id CHAR(32) PRIMARY KEY, buyer_hash CHAR(64) NOT NULL UNIQUE,
        course VARCHAR(16) NOT NULL, amount INT NOT NULL, name VARCHAR(120) NOT NULL,
        email VARCHAR(254) NOT NULL, environment VARCHAR(16) NOT NULL,
        checkout_id VARCHAR(80) NULL UNIQUE, pay_url TEXT NULL, provider_order VARCHAR(80) NULL,
        state VARCHAR(24) NOT NULL DEFAULT 'CREATING', charge_id VARCHAR(80) NULL,
        fulfilled TINYINT NOT NULL DEFAULT 0, created BIGINT NOT NULL, updated BIGINT NOT NULL,
        INDEX payments_created(created)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci";
    private array $settings;
    public function __construct(private FormacaoApp $app, private string $private) {
        $file=$private.'/pagbank.json';
        $this->settings=is_file($file)?json_decode(file_get_contents($file),true,32,JSON_THROW_ON_ERROR):[
            'token'=>$app->config['pagbank_token']??'',
            'environment'=>$app->config['pagbank_environment']??'sandbox',
            'enabled'=>$app->config['pagbank_enabled']??false,
        ];
    }
    private function json(int $status,array $body): never {
        http_response_code($status);header('Content-Type: application/json; charset=utf-8');
        header('Cache-Control: no-store');echo json_encode($body,JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR);exit;
    }
    private function fail(int $status,string $message): never {$this->json($status,['error'=>$message]);}
    private function ready(): bool {return !empty($this->settings['enabled']) && strlen($this->settings['token']??'')>=20;}
    private function install(): void {$this->app->db->exec(self::SCHEMA);}
    private function request(string $path,?array $payload=null): array {
        // Host and paths are fixed server-side; never follow URLs provided by webhook callers.
        $base=($this->settings['environment']??'sandbox')==='production'?'https://api.pagseguro.com':'https://sandbox.api.pagseguro.com';
        $body=$payload===null?null:json_encode($payload,JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR);
        $headers=['Authorization: Bearer '.$this->settings['token'],'Accept: application/json','Content-Type: application/json'];
        if($payload!==null)$headers[]='x-idempotency-key: '.$payload['reference_id'];
        $context=stream_context_create(['http'=>['method'=>$payload===null?'GET':'POST','header'=>implode("\r\n",$headers),'content'=>$body??'','timeout'=>15,'ignore_errors'=>true,'follow_location'=>0], 'ssl'=>['verify_peer'=>true,'verify_peer_name'=>true]]);
        $response=@file_get_contents($base.$path,false,$context);
        $status=0;foreach($http_response_header??[] as $line)if(preg_match('~^HTTP/\S+ (\d+)~',$line,$m))$status=(int)$m[1];
        if($response===false||$status<200||$status>=300){
            // Keep only status/error identifiers. Never persist provider payloads or credentials.
            $codes=[];$parameters=[];$failure=json_decode($response?:'{}',true);
            foreach(is_array($failure)?($failure['error_messages']??[]):[] as $error){
                foreach(['error'=>'codes','parameter_name'=>'parameters'] as $field=>$target){$value=$error[$field]??'';if(is_string($value)&&preg_match('/^[A-Za-z0-9_.\\[\\]-]{1,100}$/D',$value)){if($target==='codes')$codes[]=$value;else $parameters[]=$value;}}
            }
            $diagnostic=['http_status'=>$status,'codes'=>array_slice($codes,0,10),'parameters'=>array_slice($parameters,0,10),'at'=>time()];
            $file=$this->private.'/pagbank-diagnostic.json';file_put_contents($file,json_encode($diagnostic,JSON_THROW_ON_ERROR),LOCK_EX);chmod($file,0600);
            error_log('PagBank: request failed HTTP '.$status);throw new RuntimeException('PagBank unavailable',$status);
        }
        @unlink($this->private.'/pagbank-diagnostic.json');
        $data=json_decode($response,true,64,JSON_THROW_ON_ERROR);
        if(!is_array($data))throw new RuntimeException('Invalid provider response');return $data;
    }
    public static function validCpf(string $cpf): bool {
        if(!preg_match('/^[0-9]{11}$/D',$cpf)||preg_match('/^(\d)\1{10}$/D',$cpf))return false;
        for($n=9;$n<11;$n++){$sum=0;for($i=0;$i<$n;$i++)$sum+=(int)$cpf[$i]*($n+1-$i);$digit=(10*$sum)%11;if($digit===10)$digit=0;if($digit!==(int)$cpf[$n])return false;}return true;
    }
    public static function signed(string $body,string $signature,string $token): bool {
        return $token!==''&&preg_match('/^[a-fA-F0-9]{64}$/D',$signature)===1&&hash_equals(hash('sha256',$token.'-'.$body),strtolower($signature));
    }
    public static function payload(array $order,string $secret,string $origin): array {
        $product=self::PRODUCTS[$order['course']];
        $return=$origin.'/checkout.html#pedido='.$order['reference_id'].'&chave='.$secret;
        return ['reference_id'=>$order['reference_id'],'expiration_date'=>gmdate('Y-m-d\TH:i:s\Z',time()+7200),
            'customer'=>$order['customer'],'customer_modifiable'=>false,
            'items'=>[['reference_id'=>$order['course'],'name'=>$product['name'],'quantity'=>1,'unit_amount'=>$product['amount']]],
            'payment_methods'=>[['type'=>'PIX'],['type'=>'CREDIT_CARD']],
            'payment_methods_configs'=>[['type'=>'CREDIT_CARD','config_options'=>[['option'=>'INSTALLMENTS_LIMIT','value'=>'3']]]],
            'redirect_url'=>$return,'return_url'=>$return,'redirect_waiting_time'=>15,
            'notification_urls'=>[$origin.'/api/payments/webhook'], 'payment_notification_urls'=>[$origin.'/api/payments/webhook']];
    }
    public static function paidCharge(array $remote,array $order): ?string {
        if(($remote['reference_id']??'')!==$order['reference_id'] || strtolower($remote['customer']['email']??'')!==$order['email'])return null;
        $items=$remote['items']??[];
        if(count($items)!==1||($items[0]['reference_id']??'')!==$order['course']||(int)($items[0]['quantity']??0)!==1||(int)($items[0]['unit_amount']??0)!==(int)$order['amount'])return null;
        foreach($remote['charges']??[] as $charge){
            $method=$charge['payment_method']??[];$amount=$charge['amount']??[];
            if(($charge['status']??'')==='PAID'&&($amount['currency']??'')==='BRL'&&(int)($amount['summary']['paid']??0)>=(int)$order['amount']&&(int)($amount['summary']['refunded']??0)===0&&in_array($method['type']??'',['PIX','CREDIT_CARD'],true)&&($method['type']!=='CREDIT_CARD'||((int)($method['installments']??0)>=1&&(int)$method['installments']<=3))&&preg_match('/^CHAR_[A-Za-z0-9-]+$/D',$charge['id']??''))return $charge['id'];
        }return null;
    }
    public static function safePayUrl(string $url): bool {
        $p=parse_url($url);return is_array($p)&&($p['scheme']??'')==='https'&&empty($p['user'])&&empty($p['pass'])&&empty($p['port'])&&in_array($p['host']??'',['pagamento.pagbank.com.br','sandbox.pagamento.pagbank.com.br','pagamento.sandbox.pagbank.com.br'],true);
    }
    private function key(): string {
        $file=$this->private.'/payment-key';
        if(!is_file($file)){
            $f=@fopen($file,'x');if($f){chmod($file,0600);fwrite($f,bin2hex(random_bytes(32)));fclose($f);}
        }
        $key=file_get_contents($file);if(strlen($key)!==64)throw new RuntimeException('Missing payment key');return $key;
    }
    private function activation(array $order): string {return hash_hmac('sha256','invite:'.$order['buyer_hash'],$this->key());}
    private function fulfill(string $ref): void {
        $this->app->db->beginTransaction();
        try{
            $o=$this->app->query('SELECT * FROM payment_orders WHERE reference_id=? FOR UPDATE',[$ref])->fetch();
            if(!$o||$o['state']!=='PAID'||(int)$o['fulfilled']||$o['environment']!=='production'){$this->app->db->commit();return;}
            // Same email lock as manual invitations. Two purchases preserve both course grants.
            $lock=hash('sha256','token:invite:'.$o['email']);
            $this->app->query('INSERT IGNORE INTO limits(key_hash,window_start,count) VALUES(?,?,0)',[$lock,time()]);
            $this->app->query('SELECT key_hash FROM limits WHERE key_hash=? FOR UPDATE',[$lock]);
            $user=$this->app->query('SELECT * FROM users WHERE email=? FOR UPDATE',[$o['email']])->fetch();
            if($user){
                // Suspended accounts require the administrator; a purchase never reactivates them.
                if(!(int)$user['active']){$this->app->db->commit();return;}
                $courses=array_values(array_unique([...json_decode($user['courses'],true),$o['course']]));
                $this->app->query('UPDATE users SET courses=? WHERE id=?',[json_encode($courses),$user['id']]);
            }else{
                $courses=[$o['course']];
                foreach($this->app->query("SELECT courses FROM access_tokens WHERE email=? AND purpose='invite' AND used=0 AND expires>?",[$o['email'],time()])->fetchAll() as $invite)$courses=[...$courses,...json_decode($invite['courses'],true)];
                $courses=array_values(array_unique($courses));
                // Keep older valid purchase links usable and give them the combined entitlement.
                $this->app->query("UPDATE access_tokens SET courses=? WHERE email=? AND purpose='invite' AND used=0 AND expires>?",[json_encode($courses),$o['email'],time()]);
                $raw=$this->activation($o);
                $this->app->query('INSERT IGNORE INTO access_tokens(token_hash,purpose,email,name,courses,expires) VALUES(?,?,?,?,?,?)',[hash('sha256',$raw),'invite',$o['email'],$o['name'],json_encode($courses),time()+172800]);
            }
            $this->app->query('UPDATE payment_orders SET fulfilled=1,updated=? WHERE reference_id=?',[time(),$ref]);
            $this->app->query('INSERT INTO audit(actor,event,target,created) VALUES(NULL,?,?,?)',['payment_enrolled',$o['email'],time()]);
            $this->app->db->commit();
        }catch(Throwable $e){if($this->app->db->inTransaction())$this->app->db->rollBack();throw $e;}
    }
    public function webhook(): never {
        if(($_SERVER['REQUEST_METHOD']??'')!=='POST')$this->fail(405,'Método não permitido.');
        if(strlen($this->settings['token']??'')<20)$this->fail(503,'Pagamentos indisponíveis.');
        $body=file_get_contents('php://input',false,null,0,65537);
        if(strlen($body)>65536||!self::signed($body,$_SERVER['HTTP_X_AUTHENTICITY_TOKEN']??'',$this->settings['token']))$this->fail(403,'Notificação inválida.');
        try{$event=json_decode($body,true,32,JSON_THROW_ON_ERROR);}catch(JsonException){$this->fail(400,'JSON inválido.');}
        if(!is_array($event))$this->fail(400,'Evento inválido.');
        $this->install();$ref=$event['reference_id']??'';
        if(!is_string($ref)||!preg_match('/^[a-f0-9]{32}$/D',$ref))$this->json(200,['received'=>true]);
        $o=$this->app->query('SELECT * FROM payment_orders WHERE reference_id=?',[$ref])->fetch();
        if(!$o||$o['environment']!==$this->settings['environment'])$this->json(200,['received'=>true]);
        $id=$event['id']??'';
        if(!is_string($id)||!preg_match('/^ORDE_[A-Za-z0-9-]+$/D',$id))$this->json(200,['received'=>true]);
        try{
            $remote=$this->request('/orders/'.rawurlencode($id));
            if(($remote['reference_id']??'')!==$ref)$this->json(200,['received'=>true]);
            // Record reversals for review and block unused purchase activation links.
            if($o['charge_id'])foreach($remote['charges']??[] as $c)if(($c['id']??'')===$o['charge_id']&&((int)($c['amount']['summary']['refunded']??0)>0||($c['status']??'')==='CANCELED')){
                $this->app->query("UPDATE payment_orders SET state='REVIEW',updated=? WHERE reference_id=?",[time(),$ref]);
                $this->app->query('UPDATE access_tokens SET used=1 WHERE token_hash=?',[hash('sha256',$this->activation($o))]);
                $this->json(200,['received'=>true]);
            }
            $charge=self::paidCharge($remote,$o);
            if($charge){
                $this->app->query("UPDATE payment_orders SET state='PAID',provider_order=?,charge_id=?,updated=? WHERE reference_id=?",[$id,$charge,time(),$ref]);
                $this->fulfill($ref);
            }elseif($o['state']!=='PAID'){
                $states=array_column($remote['charges']??[],'status');
                $state=in_array('IN_ANALYSIS',$states,true)?'IN_ANALYSIS':(in_array('WAITING',$states,true)?'WAITING':(in_array('DECLINED',$states,true)?'DECLINED':'WAITING'));
                $this->app->query('UPDATE payment_orders SET state=?,updated=? WHERE reference_id=? AND state<>? ',[$state,time(),$ref,'PAID']);
            }
        }catch(Throwable){$this->fail(503,'A confirmação será processada novamente.');}
        $this->json(200,['received'=>true]);
    }
    public function publicRoute(string $path,string $method,array $data): never {
        if($path==='/api/payments/config'&&$method==='GET')$this->json(200,['enabled'=>$this->ready(),'environment'=>$this->settings['environment'],'products'=>self::PRODUCTS]);
        if($path==='/api/payments/create'&&$method==='POST'){
            if(!$this->ready())$this->fail(503,'O pagamento online está sendo preparado. Fale com Luís Fernando para se matricular.');
            foreach(['key','course','name','email','cpf','phone'] as $field)if(!is_string($data[$field]??null))$this->fail(400,'Dados de matrícula inválidos.');
            $secret=$data['key'];$course=$data['course'];$name=trim($data['name']);$email=strtolower(trim($data['email']));
            $cpf=preg_replace('/\D/','',$data['cpf']??'');$phone=preg_replace('/\D/','',$data['phone']??'');
            if(!is_string($secret)||!preg_match('/^[a-f0-9]{64}$/D',$secret)||!is_string($course)||!isset(self::PRODUCTS[$course])||strlen($name)<3||strlen($name)>120||strlen($email)>254||!filter_var($email,FILTER_VALIDATE_EMAIL)||!self::validCpf($cpf)||!preg_match('/^[1-9][0-9]{9,10}$/D',$phone)||($data['accepted']??false)!==true)$this->fail(400,'Confira seus dados e confirme as informações da formação.');
            if($this->app->limited('checkout:'.($_SERVER['REMOTE_ADDR']??''),10))$this->fail(429,'Aguarde alguns minutos antes de tentar novamente.');
            $this->install();$hash=hash('sha256',$secret);$ref=bin2hex(random_bytes(16));
            $this->app->query('INSERT IGNORE INTO payment_orders(reference_id,buyer_hash,course,amount,name,email,environment,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',[$ref,$hash,$course,self::PRODUCTS[$course]['amount'],$name,$email,$this->settings['environment'],time(),time()]);
            $o=$this->app->query('SELECT * FROM payment_orders WHERE buyer_hash=?',[$hash])->fetch();
            if($o['course']!==$course||$o['email']!==$email||$o['environment']!==$this->settings['environment'])$this->fail(409,'Reabra a matrícula para atualizar os dados.');
            if($o['pay_url'])$this->json(200,['url'=>$o['pay_url'],'reference'=>$o['reference_id']]);
            $o['customer']=['name'=>$name,'email'=>$email,'tax_id'=>$cpf,'phone'=>['country'=>'+55','area'=>substr($phone,0,2),'number'=>substr($phone,2)]];
            try{
                $remote=$this->request('/checkouts',self::payload($o,$secret,$this->app->config['origin']));
                $pay='';foreach($remote['links']??[] as $link)if(($link['rel']??'')==='PAY')$pay=$link['href']??'';
                if(!self::safePayUrl($pay)||!preg_match('/^CHEC_[A-Za-z0-9-]+$/D',$remote['id']??''))throw new RuntimeException('Invalid payment link');
                $this->app->query("UPDATE payment_orders SET checkout_id=?,pay_url=?,state=IF(state='CREATING','WAITING',state),updated=? WHERE reference_id=?",[$remote['id'],$pay,time(),$o['reference_id']]);
            }catch(Throwable $e){
                $message=match($e->getCode()){
                    401=>'O PagBank recusou a autenticação. O administrador precisa conferir se o token pertence ao ambiente selecionado.',
                    403=>'O PagBank não autorizou este checkout. O administrador precisa conferir as permissões da conta.',
                    400=>'O PagBank recusou os dados do checkout. Confira os dados informados; se persistir, fale com Luís Fernando.',
                    default=>'Não foi possível abrir o PagBank agora. Tente novamente ou fale com Luís Fernando.',
                };$this->fail(503,$message);
            }
            $this->json(201,['url'=>$pay,'reference'=>$o['reference_id']]);
        }
        if($path==='/api/payments/status'&&$method==='POST'){
            $key=$data['key']??'';$ref=$data['reference']??'';
            if(!is_string($key)||!preg_match('/^[a-f0-9]{64}$/D',$key)||!is_string($ref)||!preg_match('/^[a-f0-9]{32}$/D',$ref))$this->fail(400,'Link de acompanhamento inválido.');
            if($this->app->limited('payment-status:'.($_SERVER['REMOTE_ADDR']??''),100))$this->fail(429,'Aguarde alguns minutos.');
            $this->install();$o=$this->app->query('SELECT * FROM payment_orders WHERE reference_id=? AND buyer_hash=?',[$ref,hash('sha256',$key)])->fetch();
            if(!$o)$this->fail(404,'Matrícula não encontrada.');
            $link=null;$state=$o['state'];
            if($state==='PAID'&&$o['environment']==='production'){
                $this->fulfill($ref);
                $user=$this->app->query('SELECT active FROM users WHERE email=?',[$o['email']])->fetch();
                if($user){if((int)$user['active'])$link='/entrar.html';else $state='REVIEW';}
                else{
                    $raw=$this->activation($o);$t=$this->app->query("SELECT used,expires FROM access_tokens WHERE token_hash=? AND purpose='invite'",[hash('sha256',$raw)])->fetch();
                    if($t&&!(int)$t['used']&&(int)$t['expires']>time())$link='/ativar.html#'.$raw;else $state='REVIEW';
                }
            }
            $this->json(200,['state'=>$state,'environment'=>$o['environment'],'access_url'=>$link,'course'=>$o['course']]);
        }
        $this->fail(404,'Recurso não encontrado.');
    }
    public function adminRoute(string $path,string $method,array $data): never {
        if($path==='/api/admin/payments/settings'){
            if($method==='GET'){
                $file=$this->private.'/pagbank-diagnostic.json';$diagnostic=is_file($file)?json_decode(file_get_contents($file),true):null;
                $this->json(200,['configured'=>strlen($this->settings['token']??'')>=20,'environment'=>$this->settings['environment'],'enabled'=>$this->ready(),'diagnostic'=>$diagnostic]);
            }
            if($method==='PUT'){
                $env=$data['environment']??'';$token=$data['token']??'';$enabled=$data['enabled']??null;
                if(!in_array($env,['sandbox','production'],true)||!is_string($token)||!is_bool($enabled)||strlen($token)>2048||str_contains($token,"\n")||str_contains($token,"\r"))$this->fail(400,'Configuração inválida.');
                $token=trim($token);
                if($env!==$this->settings['environment']&&$token==='')$this->fail(400,'Ao trocar de ambiente, informe o token correspondente.');
                $token=$token?:$this->settings['token'];
                if($enabled&&strlen($token)<20)$this->fail(400,'Informe o token do PagBank.');
                $config=['token'=>$token,'environment'=>$env,'enabled'=>$enabled];
                $file=tempnam($this->private,'pagbank-');if(!$file)throw new RuntimeException('Private storage unavailable');
                chmod($file,0600);file_put_contents($file,json_encode($config,JSON_THROW_ON_ERROR),LOCK_EX);
                if(!rename($file,$this->private.'/pagbank.json'))throw new RuntimeException('Private storage unavailable');
                $this->json(200,['ok'=>true]);
            }
        }
        if($path==='/api/admin/payments/orders'&&$method==='GET'){
            $this->install();$rows=$this->app->query('SELECT reference_id,course,amount,name,email,environment,state,fulfilled,created FROM payment_orders ORDER BY created DESC LIMIT 100')->fetchAll();$this->json(200,['orders'=>$rows]);
        }
        $this->fail(405,'Método não permitido.');
    }
}
