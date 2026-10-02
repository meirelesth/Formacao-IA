<?php
declare(strict_types=1);
final class FormacaoSetup {
    private static function save(string $path,array $value): void {
        $temp=$path.'.tmp.'.bin2hex(random_bytes(6));
        if(file_put_contents($temp,"<?php\nreturn ".var_export($value,true).";\n",LOCK_EX)===false)throw new RuntimeException('Cannot save settings');
        chmod($temp,0600);if(!rename($temp,$path))throw new RuntimeException('Cannot save settings');
        clearstatcache(true,$path);if(function_exists('opcache_invalidate'))opcache_invalidate($path,true);
    }
    public static function run(array $config,string $public,string $private): never {
        header('Cache-Control: no-store');header('Referrer-Policy: no-referrer');header('X-Frame-Options: DENY');header("Content-Security-Policy: default-src 'self'; script-src 'none'; style-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'");
        $key=$config['setup_key']??'';
        if(is_file($private.'/.installed')||strlen($key)<32||str_starts_with($key,'SUBSTITUA')){http_response_code(404);exit('Instalação indisponível.');}
        $error='';$factor=null;$formKey='';
        if($_SERVER['REQUEST_METHOD']==='POST'){
            if(($_SERVER['HTTP_ORIGIN']??'')!==$config['origin']||(int)($_SERVER['CONTENT_LENGTH']??0)>4096){http_response_code(403);exit('Requisição não permitida.');}
            $lock=fopen($private.'/.setup.lock','c+');chmod($private.'/.setup.lock',0600);
            if(!$lock||!flock($lock,LOCK_EX|LOCK_NB)){http_response_code(429);exit('Aguarde e tente novamente.');}
            $attemptPath=$private.'/.setup-attempts.php';$now=time();$attempt=is_file($attemptPath)?require $attemptPath:['start'=>$now,'count'=>0];
            if($attempt['start']<$now-900)$attempt=['start'=>$now,'count'=>0];
            if($attempt['count']>=10){http_response_code(429);exit('Muitas tentativas. Aguarde 15 minutos.');}
            $entered=$_POST['setup_key']??'';
            if(!is_string($entered)||!hash_equals(hash('sha256',$key),hash('sha256',$entered))){$attempt['count']++;self::save($attemptPath,$attempt);$error='Chave de instalação inválida.';}
            else {
                $formKey=$entered;$app=new FormacaoApp($config,$public,$private);$app->install();
                if((int)$app->query("SELECT COUNT(*) FROM users WHERE role='admin'")->fetchColumn()>0){http_response_code(404);exit('Instalação já concluída.');}
                $factorPath=$private.'/.setup-factor.php';$factor=is_file($factorPath)?require $factorPath:null;
                if(!$factor||$factor['expires']<time()){
                    $alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';$secret='';for($i=0;$i<32;$i++)$secret.=$alphabet[random_int(0,31)];
                    $factor=['secret'=>$secret,'expires'=>time()+3600];self::save($factorPath,$factor);
                }
                if(($_POST['phase']??'')==='create'){
                    $name=$_POST['name']??'';$email=$_POST['email']??'';$password=$_POST['password']??'';$confirm=$_POST['confirm']??'';$code=$_POST['otp']??'';
                    $valid=is_string($code)&&preg_match('/^[0-9]{6}$/D',$code);$step=null;
                    if($valid)foreach([intdiv(time(),30),intdiv(time(),30)-1,intdiv(time(),30)+1] as $candidate)if(hash_equals(FormacaoApp::totp($factor['secret'],$candidate),$code))$step=$candidate;
                    if(!is_string($name)||trim($name)===''||strlen($name)>120||!is_string($email)||strlen($email)>254||!filter_var($email,FILTER_VALIDATE_EMAIL)||!is_string($password)||$password!==$confirm||!FormacaoApp::validPassword($password)||$step===null){
                        $attempt['count']++;self::save($attemptPath,$attempt);$error='Confira nome, e-mail, senha de 12 a 256 caracteres, confirmação e código do autenticador.';
                    } else {
                        $oldConfig=$config;$hash=FormacaoApp::hashPassword($password);$config['admin_totp_secret']=$factor['secret'];$config['dummy_hash']=FormacaoApp::hashPassword(FormacaoApp::rawToken());$config['setup_key']='';
                        $app->db->beginTransaction();
                        try {
                            $app->query('INSERT INTO users(name,email,password,role,courses,otp_step,created) VALUES(?,?,?,?,?,?,?)',[trim($name),strtolower(trim($email)),$hash,'admin','["basica","avancada"]',$step,time()]);
                            self::save($private.'/config.php',$config);
                            $app->db->commit();
                        } catch(Throwable $e) {
                            if($app->db->inTransaction())$app->db->rollBack();
                            self::save($private.'/config.php',$oldConfig);
                            throw $e;
                        }
                        if(file_put_contents($private.'/.installed','installed',LOCK_EX)===false)throw new RuntimeException('Cannot lock installer');chmod($private.'/.installed',0600);
                        unlink($factorPath);flock($lock,LOCK_UN);fclose($lock);
                        self::page('<h2>Instalação concluída.</h2><p class="muted">O instalador foi desativado. Aguarde o próximo código do autenticador e entre com sua conta de professor.</p><a class="primary" href="/entrar.html">Ir para o login →</a>');
                    }
                }
            }
            flock($lock,LOCK_UN);fclose($lock);
        }elseif($_SERVER['REQUEST_METHOD']!=='GET'){http_response_code(405);exit;}
        $escape=fn($value)=>htmlspecialchars($value,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');
        if($factor){
            $content='<h2>Crie sua conta de professor.</h2><p class="muted">No aplicativo autenticador, adicione uma chave manual: TOTP, seis dígitos, SHA-1 e intervalo de 30 segundos. Guarde uma cópia offline.</p><label>Chave do autenticador</label><p class="link-output"><strong>'.$escape($factor['secret']).'</strong></p><form method="post" action="/instalar"><input type="hidden" name="phase" value="create"><input type="hidden" name="setup_key" value="'.$escape($formKey).'"><label for="name">Nome</label><input id="name" name="name" required maxlength="120" autocomplete="name"><label for="email">E-mail administrativo</label><input id="email" name="email" type="email" required maxlength="254" autocomplete="username"><label for="password">Senha</label><input id="password" name="password" type="password" minlength="12" maxlength="256" required autocomplete="new-password"><label for="confirm">Confirmar senha</label><input id="confirm" name="confirm" type="password" minlength="12" maxlength="256" required autocomplete="new-password"><label for="otp">Código do autenticador</label><input id="otp" name="otp" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" required autocomplete="one-time-code"><p id="message" role="alert">'.$escape($error).'</p><button class="primary">Concluir instalação →</button></form>';
        }else{$content='<h2>Configuração inicial.</h2><p class="muted">Use a chave definida no arquivo privado de configuração. Esta tela serve exclusivamente para instalar a plataforma.</p><form method="post" action="/instalar"><label for="setup_key">Chave de instalação</label><input id="setup_key" name="setup_key" type="password" minlength="32" maxlength="256" required autocomplete="off"><p id="message" role="alert">'.$escape($error).'</p><button class="primary">Configurar conta do professor →</button></form>';}
        self::page($content);
    }
    private static function page(string $content): never {
        header('Content-Type: text/html; charset=utf-8');
        echo '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Instalação | Luís Fernando</title><link rel="stylesheet" href="/login.css"></head><body><header class="login-header"><a class="brand" href="/"><span class="mark">L<b>F</b></span><span>LUÍS FERNANDO<br><small>FORMAÇÃO PRÁTICA EM IA</small></span></a></header><main class="login-shell"><aside class="login-story"><p class="eyebrow">ÁREA DO PROFESSOR</p><h1>Uma base.<br>Para aprender<br><em>com segurança.</em></h1><p>Contas de alunos somente por convite. Administração com senha e autenticador.</p></aside><section class="login-panel">'.$content.'</section></main></body></html>';exit;
    }
}
