<?php
declare(strict_types=1);
ini_set('display_errors', '0');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
$method=$_SERVER['REQUEST_METHOD'] ?? 'GET';
$path=parse_url($_SERVER['REQUEST_URI'] ?? '/fin/',PHP_URL_PATH);
if (!in_array($method,['GET','POST'],true) || !is_string($path) || !preg_match('~^/fin(?:/|$)~',$path)) { http_response_code(405);exit; }
if (!in_array($_SERVER['HTTPS']??'',['on','1'],true)) {http_response_code(403);exit;}
$query=$_SERVER['QUERY_STRING'] ?? '';
if (strlen($query)>500 || (int)($_SERVER['CONTENT_LENGTH']??0)>32768) {http_response_code(413);exit;}
$headers=['Content-Type: application/json'];
foreach(['HTTP_COOKIE'=>'Cookie','HTTP_ORIGIN'=>'Origin','HTTP_X_CSRF_TOKEN'=>'X-CSRF-Token'] as $key=>$name){
    $v=$_SERVER[$key]??'';
    if(is_string($v)&&$v!==''&&!preg_match('/[\r\n]/',$v))$headers[]=$name.': '.$v;
}
$body=$method==='POST'?file_get_contents('php://input',false,null,0,32769):'';
if (strlen($body)>32768) {http_response_code(413);exit;}
$context=stream_context_create(['http'=>['method'=>$method,'header'=>implode("\r\n",$headers),'content'=>$body,'timeout'=>20,'ignore_errors'=>true,'follow_location'=>0], 'ssl'=>['verify_peer'=>true,'verify_peer_name'=>true]]);
$url='https://srv1616271.hstgr.cloud'.$path.($query!==''?'?'.$query:'');
$response=@file_get_contents($url,false,$context);
if($response===false){http_response_code(503);header('Content-Type: application/json; charset=utf-8');echo '{"error":"Financeiro temporariamente indisponível."}';exit;}
$status=502;
foreach($http_response_header??[] as $h){
    if(preg_match('~^HTTP/\S+ (\d{3})~',$h,$m)){$status=(int)$m[1];continue;}
    if(preg_match('/^(Content-Type|Set-Cookie|Content-Security-Policy|X-Frame-Options|Referrer-Policy):/i',$h))header($h,false);
}
http_response_code($status);echo $response;
