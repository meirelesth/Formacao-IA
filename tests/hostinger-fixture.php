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
    $app->db->exec(Payments::SCHEMA);$app->query('DELETE FROM payment_orders');
    foreach(['sessions','progress','access_tokens','limits','mail_jobs','audit'] as $table)$app->query('DELETE FROM '.$table);
    $app->query("DELETE FROM users WHERE role='student'");$app->query('UPDATE users SET otp_step=-1');
    foreach([['Aluno A','a@example.com','senha-local-123456','basica'],['Aluno B','b@example.com','senha-local-654321','avancada']] as [$name,$email,$pass,$course])$app->query('INSERT INTO users(name,email,password,courses,created) VALUES(?,?,?,?,?)',[$name,$email,FormacaoApp::hashPassword($pass),json_encode([$course]),time()]);
}elseif($mode==='seed-payments'){
    foreach([['1','newpay@example.com','basica','PAID','production'],['2','newpay@example.com','avancada','PAID','production'],['3','testpay@example.com','basica','PAID','sandbox'],['4','waiting@example.com','basica','WAITING','production'],['5','a@example.com','avancada','PAID','production'],['6','admin-test@example.com','admin_test','PAID','production']] as [$digit,$email,$course,$state,$env]){
        $app->query('INSERT INTO payment_orders(reference_id,buyer_hash,course,amount,name,email,environment,state,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)',[str_repeat($digit,32),hash('sha256',str_repeat($digit,64)),$course,$course==='admin_test'?100:Payments::PRODUCTS[$course]['amount'],'Payment Student',$email,$env,$state,time(),time()]);
    }
}elseif($mode==='inspect-payments'){
    echo json_encode(['orders'=>$app->query('SELECT state,fulfilled FROM payment_orders ORDER BY reference_id')->fetchAll(),'invites'=>$app->query("SELECT email,courses,token_hash FROM access_tokens WHERE purpose='invite'")->fetchAll()]);
}elseif($mode==='expire-session')$app->query('UPDATE sessions SET expires=0');
elseif($mode==='idle-session')$app->query('UPDATE sessions SET last_seen=0');
elseif($mode==='expire-token')$app->query('UPDATE access_tokens SET expires=0');
elseif($mode==='inspect'){
    $users=$app->query('SELECT email,password,role,active FROM users')->fetchAll();$tokens=$app->query('SELECT token_hash,used FROM access_tokens')->fetchAll();$sessions=$app->query('SELECT token_hash,csrf FROM sessions')->fetchAll();$jobs=$app->query('SELECT email FROM mail_jobs')->fetchAll();echo json_encode(compact('users','tokens','sessions','jobs'));
}elseif($mode==='fill-queue'){
    $app->db->beginTransaction();
    for($i=0;$i<1000;$i++)$app->query('INSERT INTO mail_jobs(email,purpose,available,created) VALUES(?,?,?,?)',['queued@example.com','reset',time(),time()]);
    $app->db->commit();
}elseif($mode==='run-cron')require '/var/www/formacao-private/cron.php';
