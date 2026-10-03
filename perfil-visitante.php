<?php
declare(strict_types=1);
ini_set('display_errors', '0');
// Standalone entrypoint for Hostinger: all credentials remain outside public_html.
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
function profileResponse(int $status, array $data): never {
    http_response_code($status);
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);
    exit;
}
$private = getenv('FORMACAO_PRIVATE_DIR') ?: dirname(__DIR__).'/formacao-private';
$configFile = $private.'/config.php';
if (!is_file($configFile)) profileResponse(503, ['enabled'=>false,'error'=>'O formulário aguarda a configuração do banco na hospedagem.']);
try {
    $config = require $configFile;
    if (!is_array($config)) throw new RuntimeException('Invalid config');
    require_once __DIR__.'/perfil-visitante-lib.php';
    if (!preg_match('/^[A-Za-z0-9_]+$/D', $config['db_name'] ?? '')) throw new RuntimeException('Invalid database');
    $db = new PDO('mysql:host='.$config['db_host'].';port='.($config['db_port']??3306).';dbname='.$config['db_name'].';charset=utf8mb4', $config['db_user'], $config['db_password'], [
        PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC, PDO::ATTR_EMULATE_PREPARES=>false,
    ]);
    $method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
    $enabled = VisitorProfile::ready($config);
    if ($method === 'GET' && isset($_GET['config'])) profileResponse(200, ['enabled'=>$enabled]);
    if ($method === 'GET' && isset($_GET['responses'])) {
        $raw = $_COOKIE['lf_session'] ?? '';
        if (!is_string($raw) || strlen($raw) > 200) profileResponse(401, ['error'=>'Entre como administrador para consultar as respostas.']);
        $q = $db->prepare('SELECT u.role,s.last_seen FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>? AND u.active=1');
        $q->execute([hash('sha256', $raw), time()]);
        $user = $q->fetch();
        if (!$user) profileResponse(401, ['error'=>'Entre como administrador para consultar as respostas.']);
        if ((int)$user['last_seen'] < time()-900) profileResponse(401, ['error'=>'Sessão expirada. Entre novamente como administrador.']);
        if ($user['role'] !== 'admin') profileResponse(403, ['error'=>'Acesso exclusivo do administrador.']);
        $db->exec(VisitorProfile::SCHEMA);
        $q = $db->query('SELECT request_id,payload,state,created FROM visitor_profiles ORDER BY created DESC LIMIT 200');
        $items = [];
        foreach ($q as $row) $items[] = ['id'=>$row['request_id'],'created'=>(int)$row['created'],'delivery_status'=>$row['state'],'answers'=>json_decode($row['payload'],true,512,JSON_THROW_ON_ERROR)];
        profileResponse(200, ['responses'=>$items,'limit'=>200]);
    }
    if ($method !== 'POST') profileResponse(405, ['error'=>'Método não permitido.']);
    if (!$enabled) profileResponse(503, ['error'=>'O formulário ainda não está disponível.']);
    if (($_SERVER['HTTP_ORIGIN'] ?? '') !== ($config['origin'] ?? '')) profileResponse(403, ['error'=>'Origem não permitida.']);
    if (strtolower(trim(explode(';', $_SERVER['CONTENT_TYPE'] ?? '')[0])) !== 'application/json') profileResponse(415, ['error'=>'Envie JSON.']);
    $body = file_get_contents('php://input', false, null, 0, 4097);
    if (!is_string($body) || strlen($body) === 0 || strlen($body) > 4096) profileResponse(413, ['error'=>'Requisição inválida.']);
    try {
        $object = json_decode($body, false, 512, JSON_THROW_ON_ERROR);
        if (!$object instanceof stdClass) profileResponse(400, ['error'=>'JSON inválido.']);
        $data = json_decode($body, true, 512, JSON_THROW_ON_ERROR);
    } catch (JsonException) { profileResponse(400, ['error'=>'JSON inválido.']); }
    $profile = VisitorProfile::validate($data);
    if ($profile === null) profileResponse(400, ['error'=>'Confira as opções selecionadas e o tamanho dos campos.']);
    // Reuse the existing private database without depending on the main API router.
    $db->exec('CREATE TABLE IF NOT EXISTS visitor_profile_limits (key_hash CHAR(64) PRIMARY KEY, window_start BIGINT NOT NULL, count INT NOT NULL) ENGINE=InnoDB');
    $db->beginTransaction();
    $key = hash('sha256', 'profile:'.($_SERVER['REMOTE_ADDR'] ?? ''));
    $q = $db->prepare('INSERT IGNORE INTO visitor_profile_limits(key_hash,window_start,count) VALUES(?,?,0)');
    $q->execute([$key,time()]);
    $q = $db->prepare('SELECT window_start,count FROM visitor_profile_limits WHERE key_hash=? FOR UPDATE');
    $q->execute([$key]);$limit=$q->fetch();
    $fresh = (int)$limit['window_start'] < time()-900;
    $count = $fresh ? 1 : (int)$limit['count']+1;
    $q = $db->prepare('UPDATE visitor_profile_limits SET window_start=?,count=? WHERE key_hash=?');
    $q->execute([$fresh?time():(int)$limit['window_start'],$count,$key]);
    $db->commit();
    if ($count > 5) profileResponse(429, ['error'=>'Muitas tentativas. Tente novamente mais tarde.']);
    $db->exec(VisitorProfile::SCHEMA);
    $q = $db->prepare('INSERT IGNORE INTO visitor_profiles(request_id,payload,available,created) VALUES(?,?,?,?)');
    $q->execute([$profile['request_id'],json_encode($profile,JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR),time(),time()]);
    $db->exec('DELETE FROM visitor_profile_limits WHERE window_start < '.(time()-86400));
    profileResponse(202, ['ok'=>true,'message'=>'Respostas registradas. Obrigado por participar.']);
} catch (Throwable) {
    if (isset($db) && $db->inTransaction()) $db->rollBack();
    error_log('Formacao: visitor profile unavailable; no credentials or personal data logged');
    profileResponse(503, ['enabled'=>false,'error'=>'Não foi possível registrar agora. Tente novamente mais tarde.']);
}
