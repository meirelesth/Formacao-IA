<?php
// TEST-ONLY fixture. Never copied into the deployment package.
if(PHP_SAPI!=='cli'||getenv('LF_TEST_ALLOW')!=='1')exit(1);
require '/var/www/formacao-private/app/App.php';$path='/var/www/formacao-private/config.php';
$mode=$argv[1]??'reset';
if($mode==='configure'){
    $cfg=['origin'=>'http://127.0.0.1:8080','allow_http'=>true,'db_host'=>'127.0.0.1','db_port'=>3306,'db_name'=>'formacao_test','db_user'=>'test','db_password'=>'test-only-password','setup_key'=>'fixture-setup-key-32-characters-abcdef','admin_totp_secret'=>'','smtp_host'=>'','smtp_from'=>''];
    file_put_contents($path,"<?php return ".var_export($cfg,true).';');chmod($path,0600);chown($path,'www-data');exit;
}
$cfg=require $path;$app=new FormacaoApp($cfg,'/var/www/html','/var/www/formacao-private');
if($mode==='reset'){
    foreach(['sessions','progress','access_tokens','limits','mail_jobs','audit'] as $table)$app->query('DELETE FROM '.$table);
    $app->query("DELETE FROM users WHERE role='student'");$app->query('UPDATE users SET otp_step=-1');
    foreach([['Aluno A','a@example.com','senha-local-123456','basica'],['Aluno B','b@example.com','senha-local-654321','avancada']] as [$name,$email,$pass,$course])$app->query('INSERT INTO users(name,email,password,courses,created) VALUES(?,?,?,?,?)',[$name,$email,FormacaoApp::hashPassword($pass),json_encode([$course]),time()]);
}elseif($mode==='expire-session')$app->query('UPDATE sessions SET expires=0');
elseif($mode==='idle-session')$app->query('UPDATE sessions SET last_seen=0');
elseif($mode==='expire-token')$app->query('UPDATE access_tokens SET expires=0');
elseif($mode==='inspect'){
    $users=$app->query('SELECT email,password,role,active FROM users')->fetchAll();$tokens=$app->query('SELECT token_hash,used FROM access_tokens')->fetchAll();$sessions=$app->query('SELECT token_hash,csrf FROM sessions')->fetchAll();$jobs=$app->query('SELECT email FROM mail_jobs')->fetchAll();echo json_encode(compact('users','tokens','sessions','jobs'));
}elseif($mode==='run-cron')require '/var/www/formacao-private/cron.php';
