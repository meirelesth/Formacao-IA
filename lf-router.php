<?php
declare(strict_types=1);
ini_set('display_errors', '0');
header('X-Content-Type-Options: nosniff');
header('Cache-Control: no-store');
$private = getenv('FORMACAO_PRIVATE_DIR') ?: dirname(__DIR__).'/formacao-private';
try {
    if (!is_file($private.'/config.php')) {
        http_response_code(503);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode(['error'=>'O acesso à plataforma aguarda configuração na hospedagem.']);
        exit;
    }
    $config = require $private.'/config.php';
    if (str_starts_with($config['origin'] ?? '', 'https://') && !in_array($_SERVER['HTTPS'] ?? '', ['on','1'], true)) {
        http_response_code(308);
        header('Location: '.$config['origin'].'/');
        exit;
    }
    // Git deployment keeps application sources in hostinger/app; credentials stay private.
    $application = __DIR__.'/hostinger/app/App.php';
    require $application;
    $app = new FormacaoApp($config, __DIR__, $private);
    $path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
    if ($path === '/instalar') {
        require __DIR__.'/hostinger/app/Setup.php';
        FormacaoSetup::run($config, __DIR__, $private);
    }
    $app->handle();
} catch (Throwable $e) {
    error_log('Formacao: internal request failure ('.get_class($e).':'.(int)$e->getCode().')');
    http_response_code(503);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['error'=>'Serviço temporariamente indisponível. Verifique a instalação da plataforma na hospedagem.']);
}
