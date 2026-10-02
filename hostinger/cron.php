<?php
declare(strict_types=1);
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
umask(0077);require __DIR__.'/app/App.php';require __DIR__.'/vendor/autoload.php';
$config=require __DIR__.'/config.php';$app=new FormacaoApp($config,dirname(__DIR__).'/public_html',__DIR__);
// One runner; the queue remains durable across requests and cron restarts.
$lock=fopen(__DIR__.'/.mail.lock','c+');if(!$lock||!flock($lock,LOCK_EX|LOCK_NB))exit;
$app->query('DELETE FROM sessions WHERE expires<=?',[time()]);
$app->query('DELETE FROM access_tokens WHERE expires<?',[time()-86400]);
$app->query('DELETE FROM limits WHERE window_start<?',[time()-86400]);
$app->query('DELETE FROM audit WHERE created<?',[time()-180*86400]);
$jobs=$app->query('SELECT * FROM mail_jobs WHERE available<=? ORDER BY id LIMIT 20',[time()])->fetchAll();
foreach($jobs as $job){
    $id=(int)$job['id'];$raw=null;
    try{
        $user=$app->query('SELECT id FROM users WHERE email=? AND active=1',[$job['email']])->fetch();
        if(!$user||empty($config['smtp_host'])||empty($config['smtp_from'])){$app->query('DELETE FROM mail_jobs WHERE id=?',[$id]);continue;}
        // Invalidate the last token on retry so only the delivered link remains valid.
        $raw=$app->token('reset',$job['email'],'',[],(int)$user['id']);
        $app->query('UPDATE mail_jobs SET token_hash=? WHERE id=?',[hash('sha256',$raw),$id]);
        $mail=new PHPMailer\PHPMailer\PHPMailer(true);$mail->isSMTP();$mail->Host=$config['smtp_host'];$mail->Port=(int)($config['smtp_port']??587);$mail->Timeout=15;
        $mail->SMTPSecure=$mail->Port===465?PHPMailer\PHPMailer\PHPMailer::ENCRYPTION_SMTPS:PHPMailer\PHPMailer\PHPMailer::ENCRYPTION_STARTTLS;
        $mail->SMTPAuth=!empty($config['smtp_user']);$mail->Username=$config['smtp_user']??'';$mail->Password=$config['smtp_password']??'';
        $mail->SMTPOptions=['ssl'=>['verify_peer'=>true,'verify_peer_name'=>true,'allow_self_signed'=>false]];$mail->CharSet='UTF-8';
        $mail->setFrom($config['smtp_from'],'Luís Fernando · Formação IA');$mail->addAddress($job['email']);$mail->Subject='Redefina sua senha — Formação IA Luís Fernando';
        $mail->Body="Use este link para redefinir sua senha (válido por 30 minutos):\n\n".$config['origin'].'/redefinir.html#'.$raw."\n\nSe não reconhece a solicitação, ignore esta mensagem.";
        $mail->send();$app->query('DELETE FROM mail_jobs WHERE id=?',[$id]);
    }catch(Throwable){
        if($raw!==null)$app->query('UPDATE access_tokens SET used=1 WHERE token_hash=?',[hash('sha256',$raw)]);
        $attempts=(int)$job['attempts']+1;
        if($attempts>=3)$app->query('DELETE FROM mail_jobs WHERE id=?',[$id]);
        else $app->query('UPDATE mail_jobs SET attempts=?,available=? WHERE id=?',[$attempts,time()+300,$id]);
        error_log('Formacao: delivery failed; no credentials or tokens logged');
    }
}
flock($lock,LOCK_UN);fclose($lock);
