<?php
declare(strict_types=1);
require_once __DIR__.'/VisitorProfile.php';
require_once __DIR__.'/Payments.php';
final class FormacaoApp {
    public PDO $db;
    public array $config;
    private string $public;
    private string $private;
    private bool $secure;
    public function __construct(array $config, string $public, string $private) {
        $this->config=$config; $this->public=$public; $this->private=$private;
        $origin=$config['origin']??'';
        if (!preg_match('~^https?://[a-zA-Z0-9.-]+(?::[0-9]+)?$~D',$origin)) throw new RuntimeException('Invalid origin');
        $this->secure=str_starts_with($origin,'https://');
        if (!$this->secure && empty($config['allow_http'])) throw new RuntimeException('HTTPS required');
        if (!preg_match('/^[A-Za-z0-9_]+$/D',$config['db_name']??'')) throw new RuntimeException('Invalid database');
        $this->db=new PDO('mysql:host='.$config['db_host'].';port='.($config['db_port']??3306).';dbname='.$config['db_name'].';charset=utf8mb4', $config['db_user'],$config['db_password'],[
            PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES=>false, PDO::MYSQL_ATTR_MULTI_STATEMENTS=>false,
        ]);
    }
    public function query(string $sql,array $values=[]): PDOStatement {
        $q=$this->db->prepare($sql);$q->execute($values);return $q;
    }
    public function install(): void {
        foreach(explode(';',file_get_contents($this->private.'/schema.sql')) as $sql) if(trim($sql)!=='') $this->db->exec($sql);
    }
    public static function validPassword(string $password): bool {
        if(strlen($password)>1024||str_contains($password,"\0"))return false;
        $characters=preg_match_all('/./us',$password);
        return $characters!==false&&$characters>=6&&$characters<=256;
    }
    public static function hashPassword(string $password): string {
        if (!self::validPassword($password)) throw new InvalidArgumentException('Invalid password');
        if (defined('PASSWORD_ARGON2ID')) return password_hash($password,PASSWORD_ARGON2ID,['memory_cost'=>32768,'time_cost'=>3,'threads'=>1]);
        $salt=bin2hex(random_bytes(16));
        return 'pbkdf2$'.$salt.'$'.hash_pbkdf2('sha256',$password,hex2bin($salt),600000,64);
    }
    public static function passwordMatches(string $password,string $stored): bool {
        if (str_starts_with($stored,'pbkdf2$')) {
            $parts=explode('$',$stored);
            return count($parts)===3 && hash_equals($parts[2],hash_pbkdf2('sha256',$password,hex2bin($parts[1]),600000,64));
        }
        return password_verify($password,$stored);
    }
    public static function rawToken(): string { return rtrim(strtr(base64_encode(random_bytes(32)),'+/','-_'),'='); }
    public static function totp(string $secret,int $step): string {
        $alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';$bits='';
        foreach(str_split(strtoupper($secret)) as $letter) { $n=strpos($alphabet,$letter); if($n===false) throw new InvalidArgumentException('Invalid TOTP secret'); $bits.=str_pad(decbin($n),5,'0',STR_PAD_LEFT); }
        $key='';for($i=0;$i+8<=strlen($bits);$i+=8)$key.=chr(bindec(substr($bits,$i,8)));
        if(strlen($key)<20)throw new InvalidArgumentException('TOTP secret too short');
        $hash=hash_hmac('sha1',pack('N2',intdiv($step,4294967296),$step%4294967296),$key,true);$offset=ord($hash[19])&15;
        $n=unpack('N',substr($hash,$offset,4))[1]&0x7fffffff;
        return str_pad((string)($n%1000000),6,'0',STR_PAD_LEFT);
    }
    private function otpStep(mixed $code): ?int {
        $secret=$this->config['admin_totp_secret']??'';
        if(!is_string($code)||!preg_match('/^[0-9]{6}$/D',$code)||!preg_match('/^[A-Z2-7]{32,64}$/D',$secret))return null;
        $now=intdiv(time(),30);
        foreach([$now,$now-1,$now+1] as $step)if(hash_equals(self::totp($secret,$step),$code))return $step;
        return null;
    }
    public function limited(string $key,int $maximum): bool {
        $hash=hash('sha256',$key);$now=time();$this->db->beginTransaction();
        $this->query('INSERT IGNORE INTO limits(key_hash,window_start,count) VALUES(?,?,0)',[$hash,$now]);
        $row=$this->query('SELECT * FROM limits WHERE key_hash=? FOR UPDATE',[$hash])->fetch();
        $count=$row['window_start']<=$now-900 ? 0 : (int)$row['count'];
        if($count>=$maximum){$this->db->commit();return true;}
        $this->query('UPDATE limits SET count=?,window_start=? WHERE key_hash=?',[$count+1,$count===0?$now:$row['window_start'],$hash]);$this->db->commit();return false;
    }
    private function audit(?int $actor,string $event,?string $target=null): void { $this->query('INSERT INTO audit(actor,event,target,created) VALUES(?,?,?,?)',[$actor,$event,$target,time()]); }
    private function session(): ?array {
        $raw=$_COOKIE['lf_session']??'';if(!is_string($raw)||strlen($raw)>128)return null;
        $s=$this->query('SELECT s.*,u.name,u.email,u.role,u.courses FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>? AND u.active=1',[hash('sha256',$raw),time()])->fetch();
        if(!$s)return null;
        if((int)$s['last_seen']<time()-($s['role']==='admin'?900:1800)){$this->query('DELETE FROM sessions WHERE token_hash=?',[$s['token_hash']]);return null;}
        $this->query('UPDATE sessions SET last_seen=? WHERE token_hash=?',[time(),$s['token_hash']]);return $s;
    }
    private function cookie(string $token,int $seconds): void {setcookie('lf_session',$token,['expires'=>time()+$seconds,'path'=>'/','secure'=>$this->secure,'httponly'=>true,'samesite'=>'Lax']);}
    private function json(int $status,array $payload): never {http_response_code($status);header('Content-Type: application/json; charset=utf-8');echo json_encode($payload,JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR);exit;}
    private function fail(int $status,string $message): never {$this->json($status,['error'=>$message]);}
    private function csrf(array $data,array $session): void {if(!is_string($data['csrf']??null)||!hash_equals($session['csrf'],$data['csrf']))$this->fail(403,'Sessão inválida. Recarregue a página.');}
    private function catalog(array $session): array {
        $catalog=json_decode(file_get_contents($this->private.'/catalogo.json'),true,512,JSON_THROW_ON_ERROR);
        if($session['role']==='admin')return $catalog;
        $allowed=json_decode($session['courses'],true,512,JSON_THROW_ON_ERROR);$all=[];$paths=[];
        foreach($catalog['courses'] as $c)foreach($c['modules'] as $m)foreach($m['lessons'] as $l)$all[]=$l['material']??'';
        $catalog['courses']=array_values(array_filter($catalog['courses'],fn($c)=>in_array($c['id'],$allowed,true)));
        foreach($catalog['courses'] as $c)foreach($c['modules'] as $m)foreach($m['lessons'] as $l)$paths[]=$l['material']??'';
        $catalog['materials']=array_values(array_filter($catalog['materials'],fn($m)=>!in_array($m['path'],$all,true)||in_array($m['path'],$paths,true)));
        return $catalog;
    }
    private function validCourses(mixed $courses): bool {if(!is_array($courses)||!array_is_list($courses)||count($courses)>2)return false;foreach($courses as $course)if(!is_string($course)||!in_array($course,['basica','avancada'],true))return false;return count(array_unique($courses))===count($courses);}
    public function token(string $purpose,string $email,string $name='',array $courses=[],?int $id=null): string {
        $raw=self::rawToken();$this->db->beginTransaction();
        // Serialize replacement for a given e-mail/purpose, without storing raw tokens.
        $this->query('INSERT IGNORE INTO limits(key_hash,window_start,count) VALUES(?,?,0)',[hash('sha256','token:'.$purpose.':'.$email),time()]);
        $this->query('SELECT key_hash FROM limits WHERE key_hash=? FOR UPDATE',[hash('sha256','token:'.$purpose.':'.$email)]);
        $this->query('UPDATE access_tokens SET used=1 WHERE email=? AND purpose=?',[$email,$purpose]);
        $this->query('INSERT INTO access_tokens(token_hash,purpose,email,name,courses,user_id,expires) VALUES(?,?,?,?,?,?,?)',[hash('sha256',$raw),$purpose,$email,$name,json_encode($courses),$id,time()+($purpose==='invite'?172800:1800)]);
        $this->db->commit();return $raw;
    }
    public function handle(): never {
        header('X-Content-Type-Options: nosniff');header('Referrer-Policy: same-origin');header('X-Frame-Options: DENY');header('Cache-Control: no-store');
        header("Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' https://cdn.jsdelivr.net; media-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'");
        if($this->secure)header('Strict-Transport-Security: max-age=31536000');
        $method=$_SERVER['REQUEST_METHOD'];$url=parse_url($_SERVER['REQUEST_URI'],PHP_URL_PATH);
        if(!is_string($url))$this->fail(400,'Caminho inválido.');
        $decoded=rawurldecode($url);if(str_contains($decoded,"\0")||str_contains($decoded,'\\'))$this->fail(400,'Caminho inválido.');
        $parts=[];foreach(explode('/',$decoded) as $part){if($part==='..')array_pop($parts);elseif($part!==''&&$part!=='.')$parts[]=$part;}$path='/'.implode('/',$parts);
        if(!in_array($method,['GET','POST','PUT'],true))$this->fail(405,'Método não permitido.');
        if($path==='/api/payments/webhook')(new Payments($this,$this->private))->webhook();
        $data=[];
        if($method!=='GET'){
            if(($_SERVER['HTTP_ORIGIN']??'')!==$this->config['origin'])$this->fail(403,'Origem não permitida.');
            if(strtolower(trim(explode(';',$_SERVER['CONTENT_TYPE']??'')[0]))!=='application/json')$this->fail(415,'Envie JSON.');
            $body=file_get_contents('php://input',false,null,0,4097);
            if(strlen($body)>4096||strlen($body)===0)$this->fail(413,'Requisição inválida.');
            try{$obj=json_decode($body,false,512,JSON_THROW_ON_ERROR);if(!$obj instanceof stdClass)$this->fail(400,'JSON inválido.');$data=json_decode($body,true,512,JSON_THROW_ON_ERROR);}catch(JsonException){$this->fail(400,'JSON inválido.');}
        }
        if($path==='/healthz'&&$method==='GET'){$this->query('SELECT 1');$this->json(200,['ok'=>true]);}
        if($path==='/api/visitor-profile/config'&&$method==='GET')$this->json(200,['enabled'=>VisitorProfile::ready($this->config)]);
        if($path==='/api/visitor-profile'&&$method==='POST'){
            if(!VisitorProfile::ready($this->config))$this->fail(503,'O formulário ainda não está disponível para envio.');
            if($this->limited('visitor-profile:'.($_SERVER['REMOTE_ADDR']??''),5))$this->fail(429,'Muitas tentativas. Tente novamente mais tarde.');
            $profile=VisitorProfile::validate($data);
            if($profile===null)$this->fail(400,'Confira as opções selecionadas e o tamanho dos campos.');
            $this->db->exec(VisitorProfile::SCHEMA);
            // A retry with the same request id keeps one durable response.
            $this->query('INSERT IGNORE INTO visitor_profiles(request_id,payload,available,created) VALUES(?,?,?,?)',[$profile['request_id'],json_encode($profile,JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR),time(),time()]);
            $this->json(202,['ok'=>true,'message'=>'Respostas registradas. Obrigado por participar.']);
        }
        if(str_starts_with($path,'/api/payments/'))(new Payments($this,$this->private))->publicRoute($path,$method,$data);
        $needsSession=str_starts_with($path,'/api/')||in_array($path,['/catalogo.json','/aluno.html','/admin.html'],true)||str_starts_with($path,'/materiais/');
        $session=$needsSession?$this->session():null;$ip=$_SERVER['REMOTE_ADDR']??'';
        if($path==='/api/session'&&$method==='GET')$this->json(200,$session?['authenticated'=>true,'user'=>['name'=>$session['name'],'email'=>$session['email'],'role'=>$session['role']],'csrf'=>$session['csrf']]:['authenticated'=>false]);
        if($path==='/api/login'&&$method==='POST'){
            $email=$data['email']??'';$password=$data['password']??'';
            if(!is_string($email)||!is_string($password)||strlen($email)>254||strlen($password)>1024||str_contains($password,"\0"))$this->fail(400,'Dados de acesso inválidos.');
            $email=strtolower(trim($email));
            if($this->limited('login-ip:'.$ip,20)||$this->limited('login-email:'.$email,5))$this->fail(429,'Muitas tentativas. Aguarde 15 minutos.');
            $user=$this->query('SELECT * FROM users WHERE email=?',[$email])->fetch();
            // A fixed non-user hash uses the same configured KDF path as real accounts.
            $dummy=$this->config['dummy_hash']??null;if(!$dummy)throw new RuntimeException('Run install first',1001);
            $valid=self::passwordMatches($password,$user['password']??$dummy);
            if(!$user||!$valid||!(int)$user['active'])$this->fail(401,'E-mail ou senha inválidos.');
            $this->db->beginTransaction();$locked=$this->query('SELECT * FROM users WHERE id=? FOR UPDATE',[$user['id']])->fetch();
            if(!$locked||!(int)$locked['active']||!hash_equals($locked['password'],$user['password'])){$this->db->rollBack();$this->fail(401,'E-mail ou senha inválidos.');}
            if($user['role']==='admin'){
                $step=$this->otpStep($data['otp']??null);
                if($step===null||$step<=(int)$locked['otp_step']){$this->db->rollBack();$this->fail(401,'Acesso inválido. Confira a senha e o autenticador.');}
                $this->query('UPDATE users SET otp_step=? WHERE id=?',[$step,$user['id']]);
            }
            if($session)$this->query('DELETE FROM sessions WHERE token_hash=?',[$session['token_hash']]);
            $raw=self::rawToken();$csrf=bin2hex(random_bytes(32));
            $this->query('INSERT INTO sessions(token_hash,user_id,csrf,expires,last_seen) VALUES(?,?,?,?,?)',[hash('sha256',$raw),$user['id'],$csrf,time()+28800,time()]);
            $this->audit((int)$user['id'],'login');$this->db->commit();$this->cookie($raw,28800);
            $this->json(200,['user'=>['name'=>$user['name'],'email'=>$user['email'],'role'=>$user['role']],'csrf'=>$csrf]);
        }
        if($path==='/api/forgot-password'&&$method==='POST'){
            $email=$data['email']??'';if(!is_string($email)||strlen($email)>254||!filter_var($email,FILTER_VALIDATE_EMAIL))$this->fail(400,'Informe um e-mail válido.');$email=strtolower(trim($email));
            if($this->limited('reset-ip:'.$ip,10)||$this->limited('reset-email:'.$email,5))$this->fail(429,'Muitas solicitações. Aguarde 15 minutos.');
            // Same durable queue write for known and unknown addresses. SMTP runs in cron.
            $this->db->beginTransaction();$queueLock=hash('sha256','mail-queue');
            $this->query('INSERT IGNORE INTO limits(key_hash,window_start,count) VALUES(?,?,0)',[$queueLock,time()]);
            $this->query('SELECT key_hash FROM limits WHERE key_hash=? FOR UPDATE',[$queueLock]);
            $this->query('DELETE FROM mail_jobs WHERE created<?',[time()-86400]);
            if((int)$this->query('SELECT COUNT(*) FROM mail_jobs')->fetchColumn()<1000)$this->query('INSERT INTO mail_jobs(email,purpose,available,created) VALUES(?,?,?,?)',[$email,'reset',time(),time()]);
            $this->db->commit();
            $this->json(200,['ok'=>true,'message'=>'Se o e-mail estiver autorizado, enviaremos as instruções. Caso não receba, solicite ajuda ao professor.']);
        }
        if(in_array($path,['/api/activate','/api/reset-password'],true)&&$method==='POST'){
            if($this->limited('token-ip:'.$ip,20))$this->fail(429,'Muitas tentativas. Aguarde 15 minutos.');
            $raw=$data['token']??null;$password=$data['password']??null;
            if(!is_string($raw)||strlen($raw)>128||!is_string($password)||!self::validPassword($password))$this->fail(400,'Use o link de acesso e uma senha de 6 a 256 caracteres.');
            $purpose=$path==='/api/activate'?'invite':'reset';$hash=self::hashPassword($password);$this->db->beginTransaction();
            $t=$this->query('SELECT * FROM access_tokens WHERE token_hash=? AND purpose=? AND used=0 AND expires>? FOR UPDATE',[hash('sha256',$raw),$purpose,time()])->fetch();
            if(!$t){$this->db->rollBack();$this->fail(400,'Link inválido ou expirado.');}
            if($purpose==='invite'){
                if($this->query('SELECT id FROM users WHERE email=?',[$t['email']])->fetch()){$this->db->rollBack();$this->fail(409,'A conta já existe. Entre ou recupere sua senha.');}
                $this->query('INSERT INTO users(name,email,password,courses,created) VALUES(?,?,?,?,?)',[$t['name'],$t['email'],$hash,$t['courses'],time()]);
            }else{
                $u=$this->query('SELECT id,active FROM users WHERE id=? FOR UPDATE',[$t['user_id']])->fetch();if(!$u||!(int)$u['active']){$this->db->rollBack();$this->fail(400,'Link inválido ou expirado.');}
                $this->query('UPDATE users SET password=? WHERE id=?',[$hash,$u['id']]);$this->query('DELETE FROM sessions WHERE user_id=?',[$u['id']]);
            }
            $this->query('UPDATE access_tokens SET used=1 WHERE token_hash=?',[hash('sha256',$raw)]);$this->audit(null,$purpose,$t['email']);$this->db->commit();$this->json(200,['ok'=>true]);
        }
        if(str_starts_with($path,'/api/')){
            if(!$session)$this->fail(401,'Entre para acessar sua formação.');
            if($method!=='GET')$this->csrf($data,$session);
            if(str_starts_with($path,'/api/admin/')){if($session['role']!=='admin')$this->fail(403,'Acesso exclusivo da administração.');if(str_starts_with($path,'/api/admin/payments/'))(new Payments($this,$this->private))->adminRoute($path,$method,$data);$this->admin($path,$method,$data,$session);}
            if($path==='/api/skills')$this->skillRoute($method,$data,false);
            if(preg_match('~^/api/skills/(bundle|[0-9]+)/download$~D',$path,$match))$this->skillDownload($method,$match[1],$session);
            if($path==='/api/logout'&&$method==='POST'){$this->query('DELETE FROM sessions WHERE token_hash=?',[$session['token_hash']]);$this->cookie('',-3600);$this->json(200,['ok'=>true]);}
            if($path==='/api/progress'&&$method==='GET'){
                $rows=$this->query('SELECT lesson_id FROM progress WHERE user_id=? AND completed=1',[$session['user_id']])->fetchAll();$this->json(200,['completed'=>array_column($rows,'lesson_id')]);
            }
            if($path==='/api/progress'&&$method==='PUT'){
                $valid=[];foreach($this->catalog($session)['courses'] as $c)foreach($c['modules'] as $m)foreach($m['lessons'] as $l)if(!empty($l['available']))$valid[]=$l['id'];
                $lesson=$data['lesson']??null;$done=$data['completed']??null;if(!is_string($lesson)||!in_array($lesson,$valid,true)||!is_bool($done))$this->fail(400,'Aula ou progresso inválido.');
                $this->query('INSERT INTO progress(user_id,lesson_id,completed,updated) VALUES(?,?,?,?) ON DUPLICATE KEY UPDATE completed=VALUES(completed),updated=VALUES(updated)',[$session['user_id'],$lesson,(int)$done,time()]);$this->json(200,['ok'=>true]);
            }
            $this->fail(404,'Recurso não encontrado.');
        }
        if($method!=='GET')$this->fail(405,'Método não permitido.');
        if($path==='/catalogo.json'){if(!$session)$this->fail(401,'Entre para acessar sua formação.');$this->json(200,$this->catalog($session));}
        if(($path==='/aluno.html'&&!$session)||($path==='/admin.html'&&(!$session||$session['role']!=='admin'))){http_response_code(303);header('Location: /entrar.html');exit;}
        $relative=$path==='/'?'index.html':ltrim($path,'/');$root=$this->public;
        if(str_starts_with($relative,'materiais/')&&$relative!=='materiais/Portfolio_Formacao_IA_VIP.pdf'){
            if(!$session)$this->fail(401,'Entre para acessar o material.');$catalog=$this->catalog($session);$allowed=array_column($catalog['materials'],'path');foreach($catalog['courses'] as $c)foreach($c['modules'] as $m)foreach($m['lessons'] as $l)$allowed[]=$l['material']??'';
            if(!in_array($relative,$allowed,true))$this->fail(403,'Material não incluído na sua matrícula.');$root=$this->private;
        }else{
            $names=['checkout.html','checkout.css','checkout.js','respostas-visitantes.html','respostas-visitantes.css','respostas-visitantes.js','perfil-visitante.css','perfil-visitante.js','index.html','entrar.html','ativar.html','redefinir.html','admin.html','aluno.html','planos.html','styles.css','portfolio.css','planos.css','login.css','aluno.css','certificado.css','app.js','entrar.js','acesso.js','admin.js','aluno.js','certificado.js','favicon.ico','materiais/Portfolio_Formacao_IA_VIP.pdf'];
            if(!in_array($relative,$names,true)&&!(str_starts_with($relative,'assets/')&&in_array(strtolower(pathinfo($relative,PATHINFO_EXTENSION)),['svg','png','jpg','jpeg','ico'],true)))$this->fail(404,'Página não encontrada.');
        }
        $target=realpath($root.'/'.$relative);$base=realpath($root);
        if(!$target||!str_starts_with($target,$base.DIRECTORY_SEPARATOR)||!is_file($target))$this->fail(404,'Página não encontrada.');
        $ext=strtolower(pathinfo($target,PATHINFO_EXTENSION));$types=['html'=>'text/html','css'=>'text/css','js'=>'text/javascript','png'=>'image/png','svg'=>'image/svg+xml','jpg'=>'image/jpeg','jpeg'=>'image/jpeg','ico'=>'image/x-icon','pdf'=>'application/pdf','md'=>'text/plain'];
        header('Content-Type: '.($types[$ext]??'application/octet-stream').(in_array($ext,['html','css','js','md'],true)?'; charset=utf-8':''));header('Content-Length: '.filesize($target));readfile($target);exit;
    }
    private function importSkills(): void {
        $file=$this->private.'/skills-catalog.json';if(!is_file($file))return;
        $source=json_decode(file_get_contents($file),true,512,JSON_THROW_ON_ERROR);
        $this->db->exec("CREATE TABLE IF NOT EXISTS skills_imports(version VARCHAR(80) PRIMARY KEY) ENGINE=InnoDB");
        if($this->query('SELECT version FROM skills_imports WHERE version=?',[$source['import_version']])->fetch())return;
        $this->db->beginTransaction();
        try{
            foreach($source['skills'] as $row)$this->query('INSERT IGNORE INTO skills(id,title,category,description,version,platform,download_url,source_url,install_command,published,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?)',array_values($row));
            $this->query('INSERT IGNORE INTO skills_imports(version) VALUES(?)',[$source['import_version']]);$this->db->commit();
        }catch(Throwable $e){$this->db->rollBack();throw $e;}
    }
    private function skillDownload(string $method,string $key,array $session): never {
        $this->db->exec("CREATE TABLE IF NOT EXISTS skills (  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, title VARCHAR(120) NOT NULL,  category VARCHAR(60) NOT NULL, description TEXT NOT NULL, version VARCHAR(24) NOT NULL,  platform VARCHAR(24) NOT NULL, download_url TEXT NOT NULL, source_url TEXT NOT NULL,  install_command TEXT NOT NULL, published TINYINT NOT NULL DEFAULT 0, updated BIGINT NOT NULL ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
        $this->importSkills();
        if($method!=='GET')$this->fail(405,'Método não permitido.');
        if($key==='bundle'&&$session['role']!=='admin')$this->fail(403,'Pacote completo exclusivo da administração.');
        if($key!=='bundle'&&!$this->query('SELECT id FROM skills WHERE id=? AND published=1',[(int)$key])->fetch())$this->fail(404,'Pacote indisponível.');
        $file=$this->private.'/skills-packages.json';$packages=is_file($file)?json_decode(file_get_contents($file),true,512,JSON_THROW_ON_ERROR):[];
        $package=$packages[$key]??null;if(!$package)$this->fail(404,'Pacote indisponível.');
        $bytes=base64_decode($package['base64'],true);if($bytes===false)$this->fail(500,'Pacote inválido.');
        header('Content-Type: application/zip');header('Content-Disposition: attachment; filename="'.$package['name'].'"');header('Content-Length: '.strlen($bytes));echo $bytes;exit;
    }
    private function skillRoute(string $method,array $data,bool $admin): never {
        $this->db->exec("CREATE TABLE IF NOT EXISTS skills (  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, title VARCHAR(120) NOT NULL,  category VARCHAR(60) NOT NULL, description TEXT NOT NULL, version VARCHAR(24) NOT NULL,  platform VARCHAR(24) NOT NULL, download_url TEXT NOT NULL, source_url TEXT NOT NULL,  install_command TEXT NOT NULL, published TINYINT NOT NULL DEFAULT 0, updated BIGINT NOT NULL ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
        $this->importSkills();
        if($method==='GET'){
            $rows=$this->query('SELECT * FROM skills'.($admin?'':' WHERE published=1').' ORDER BY title,id')->fetchAll();
            foreach($rows as &$row){$row['id']=(int)$row['id'];$row['published']=(bool)$row['published'];$row['updated']=(int)$row['updated'];}unset($row);
            $this->json(200,['skills'=>$rows]);
        }
        if(!$admin||!in_array($method,['POST','PUT'],true))$this->fail(405,'Método não permitido.');
        $values=[];
        foreach(['title'=>120,'category'=>60,'description'=>500,'version'=>24,'platform'=>24,'download_url'=>1000,'source_url'=>1000,'install_command'=>800] as $field=>$limit){
            $value=$data[$field]??'';if(!is_string($value)||strlen($value)>$limit||preg_match('/[\x00-\x08\x0b\x0c\x0e-\x1f]/',$value))$this->fail(400,'Campo inválido: '.$field);$values[$field]=trim($value);
        }
        if(!$values['title']||!$values['category']||!$values['description']||!$values['version']||!in_array($values['platform'],['claude','claude-code','codex','catalog'],true)||!is_bool($data['published']??null))$this->fail(400,'Preencha os campos obrigatórios.');
        foreach(['download_url','source_url'] as $field){$u=$values[$field];if($field==='download_url'&&preg_match('~^/api/skills/[0-9]+/download$~D',$u))continue;if($u!==''&&(!filter_var($u,FILTER_VALIDATE_URL)||parse_url($u,PHP_URL_SCHEME)!=='https'||parse_url($u,PHP_URL_USER)!==null||parse_url($u,PHP_URL_PASS)!==null))$this->fail(400,'Use um link HTTPS sem credenciais.');}
        if($data['published']&&($values['platform']==='claude'&&!$values['download_url']||!in_array($values['platform'],['claude','catalog'],true)&&!$values['download_url']&&!$values['install_command']||$values['platform']==='catalog'&&!$values['source_url']))$this->fail(400,'Para publicar, informe o pacote ZIP ou o comando de instalação compatível.');
        $params=array_values($values);$params[]=(int)$data['published'];$params[]=time();
        if($method==='POST'){$this->query('INSERT INTO skills(title,category,description,version,platform,download_url,source_url,install_command,published,updated) VALUES(?,?,?,?,?,?,?,?,?,?)',$params);$id=(int)$this->db->lastInsertId();}
        else{$id=$data['id']??null;if(!is_int($id)||$id<1)$this->fail(400,'Skill inválida.');if(!$this->query('SELECT id FROM skills WHERE id=?',[$id])->fetch())$this->fail(404,'Skill não encontrada.');$params[]=$id;$this->query('UPDATE skills SET title=?,category=?,description=?,version=?,platform=?,download_url=?,source_url=?,install_command=?,published=?,updated=? WHERE id=?',$params);}
        $this->json($method==='POST'?201:200,['ok'=>true,'id'=>$id]);
    }
    private function admin(string $path,string $method,array $data,array $session): never {
        if($path==='/api/admin/skills')$this->skillRoute($method,$data,true);
        if($path==='/api/admin/students'&&$method==='GET'){
            $users=$this->query("SELECT id,name,email,active,courses FROM users WHERE role='student' ORDER BY name")->fetchAll();
            foreach($users as &$u){$u['id']=(int)$u['id'];$u['active']=(int)$u['active'];}unset($u);
            $invites=$this->query("SELECT name,email,courses,expires FROM access_tokens WHERE purpose='invite' AND used=0 AND expires>?",[time()])->fetchAll();foreach($invites as &$i)$i['expires']=(int)$i['expires'];unset($i);
            $this->json(200,['students'=>$users,'invitations'=>$invites]);
        }
        if($path==='/api/admin/invite'&&$method==='POST'){
            $name=$data['name']??null;$email=$data['email']??null;$courses=$data['courses']??null;
            if(!is_string($name)||trim($name)===''||strlen($name)>120||!is_string($email)||strlen($email)>254||!filter_var($email,FILTER_VALIDATE_EMAIL)||!$this->validCourses($courses)||!$courses)$this->fail(400,'Informe nome, e-mail e plano válido.');$email=strtolower(trim($email));
            if($this->query('SELECT id FROM users WHERE email=?',[$email])->fetch())$this->fail(409,'Este e-mail já possui uma conta.');
            $raw=$this->token('invite',$email,trim($name),$courses);$link=$this->config['origin'].'/ativar.html#'.$raw;$this->audit((int)$session['user_id'],'invited',$email);
            // Invitations are shared manually. Only the matching e-mail can log in after activation.
            $this->json(201,['link'=>$link,'sent'=>false,'expires_hours'=>48]);
        }
        if($path==='/api/admin/student'&&$method==='PUT'){
            $id=$data['id']??null;$active=$data['active']??null;$courses=$data['courses']??null;
            if(!is_int($id)||!is_bool($active)||!$this->validCourses($courses)||($active&&!$courses))$this->fail(400,'Dados inválidos.');
            $this->db->beginTransaction();$row=$this->query("SELECT id FROM users WHERE id=? AND role='student' FOR UPDATE",[$id])->fetch();if(!$row){$this->db->rollBack();$this->fail(404,'Aluno não encontrado.');}
            $this->query('UPDATE users SET active=?,courses=? WHERE id=?',[(int)$active,json_encode($courses),$id]);$this->query('DELETE FROM sessions WHERE user_id=?',[$id]);$this->audit((int)$session['user_id'],'enrollment_updated',(string)$id);$this->db->commit();$this->json(200,['ok'=>true]);
        }
        if($path==='/api/admin/reset-link'&&$method==='POST'){
            $id=$data['id']??null;if(!is_int($id))$this->fail(400,'Aluno inválido.');$user=$this->query("SELECT id,email FROM users WHERE id=? AND active=1 AND role='student'",[$id])->fetch();if(!$user)$this->fail(404,'Aluno não encontrado.');
            $raw=$this->token('reset',$user['email'],'',[],(int)$id);$this->audit((int)$session['user_id'],'reset_requested',(string)$id);$this->json(200,['link'=>$this->config['origin'].'/redefinir.html#'.$raw]);
        }
        $this->fail(404,'Recurso não encontrado.');
    }
}


