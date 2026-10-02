<?php
declare(strict_types=1);
ini_set('display_errors', '0');
header('X-Content-Type-Options: nosniff');
header('Cache-Control: no-store');
$private = dirname(__DIR__) . '/formacao-private';
try {
    if (!is_file($private . '/config.php')) {
        http_response_code(503);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode(['error'=>'A área do aluno está aguardando configuração.']);
        exit;
    }
    require $private . '/app/App.php';
    $config=require $private . '/config.php';
    if(str_starts_with($config['origin'],'https://')&&!in_array($_SERVER['HTTPS']??'', ['on','1'],true)){http_response_code(308);header('Location: '.$config['origin'].'/');exit;}
    $app = new FormacaoApp($config, __DIR__, $private);
    $path=parse_url($_SERVER['REQUEST_URI'],PHP_URL_PATH);
    if($path==='/instalar'){require $private.'/app/Setup.php';FormacaoSetup::run($config,__DIR__,$private);}
    $app->handle();
} catch (Throwable $e) {
    // Não expor SQL, credenciais, nomes ou tokens ao navegador/log.
    error_log('Formacao: internal request failure ('.get_class($e).':'.(int)$e->getCode().')');
    http_response_code(503);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['error'=>'Serviço temporariamente indisponível. Fale com o professor.']);
}
