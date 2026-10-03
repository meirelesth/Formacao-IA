<?php
declare(strict_types=1);
require __DIR__.'/../hostinger/app/Payments.php';
function check(bool $ok,string $message): void {if(!$ok)throw new RuntimeException($message);}
$body='{"status":"PAID"}';$token='fixture-token-only-not-real';
check(Payments::signed($body,hash('sha256',$token.'-'.$body),$token),'Valid signed webhook rejected');
check(!Payments::signed($body.' ',hash('sha256',$token.'-'.$body),$token),'Modified webhook accepted');
check(!Payments::signed($body,str_repeat('0',64),$token),'Forged webhook accepted');
check(!Payments::signed($body,hash('sha256','-'.$body),''),'Empty token accepted');
check(Payments::validCpf('12345678909'),'CPF checksum rejected');
check(!Payments::validCpf('11111111111')&&!Payments::validCpf('12345678900'),'Invalid CPF accepted');
$order=['reference_id'=>str_repeat('a',32),'course'=>'basica','amount'=>99700,'email'=>'student@example.com','customer'=>['email'=>'student@example.com']];
$payload=Payments::payload($order,str_repeat('b',64),'https://luisfernando.online');
check($payload['items'][0]['unit_amount']===99700,'Server price not used');
check(array_column($payload['payment_methods'],'type')===['PIX','CREDIT_CARD'],'Unrequested payment method');
check($payload['payment_methods_configs'][0]['config_options']===[['option'=>'INSTALLMENTS_LIMIT','value'=>'3']],'Incorrect installment cap');
check($payload['customer_modifiable']===false,'Buyer can change enrollment email');
check(count($payload['payment_notification_urls'])===1,'Missing payment webhook');
$remote=['reference_id'=>$order['reference_id'],'customer'=>['email'=>$order['email']],'items'=>$payload['items'],'charges'=>[['id'=>'CHAR_test-123','status'=>'PAID','amount'=>['currency'=>'BRL','summary'=>['paid'=>99700,'refunded'=>0]],'payment_method'=>['type'=>'PIX']]]];
check(Payments::paidCharge($remote,$order)==='CHAR_test-123','Paid matching order rejected');
foreach(['reference','email','price','item','currency','unpaid','refunded','installments','method'] as $case){
    $bad=$remote;
    switch($case){
        case 'reference':$bad['reference_id']='other';break;
        case 'email':$bad['customer']['email']='other@example.com';break;
        case 'price':$bad['charges'][0]['amount']['summary']['paid']=99699;break;
        case 'item':$bad['items'][0]['unit_amount']=1;break;
        case 'currency':$bad['charges'][0]['amount']['currency']='USD';break;
        case 'unpaid':$bad['charges'][0]['status']='WAITING';break;
        case 'refunded':$bad['charges'][0]['amount']['summary']['refunded']=99700;break;
        case 'installments':$bad['charges'][0]['payment_method']=['type'=>'CREDIT_CARD','installments'=>4];break;
        case 'method':$bad['charges'][0]['payment_method']['type']='BOLETO';break;
    }
    check(Payments::paidCharge($bad,$order)===null,'Accepted invalid payment: '.$case);
}
$remote['charges'][0]['payment_method']=['type'=>'CREDIT_CARD','installments'=>3];
check(Payments::paidCharge($remote,$order)!==null,'Three installments rejected');
check(Payments::safePayUrl('https://pagamento.pagbank.com.br/pagamento?code=test'),'Official PAY URL rejected');
foreach(['https://pagamento.pagbank.com.br.evil.com/a','javascript:alert(1)','http://pagamento.pagbank.com.br','https://user:pass@pagamento.pagbank.com.br','https://pagamento.pagbank.com.br:444/a'] as $url)check(!Payments::safePayUrl($url),'Unsafe PAY URL accepted');
echo "Payment signature, entitlement proof, installment limit, CPF and redirect checks passed.\n";
