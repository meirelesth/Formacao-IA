<?php
declare(strict_types=1);
require_once __DIR__.'/../hostinger/app/VisitorProfile.php';
function check(bool $condition): void { if (!$condition) throw new RuntimeException('Visitor profile contract failed'); }
$config=['visitor_survey_enabled'=>true,'visitor_survey_recipient'=>'teacher@example.test','smtp_host'=>'smtp.example.test','smtp_from'=>'site@example.test'];
check(VisitorProfile::ready($config));
check(VisitorProfile::ready([]));
check(!VisitorProfile::deliveryReady([]));
$off=$config;$off['visitor_survey_enabled']=false;check(!VisitorProfile::ready($off));
$bad=$config;$bad['visitor_survey_recipient']="teacher@example.test\r\nBcc: other@example.test";check(!VisitorProfile::deliveryReady($bad));
$sample=['request_id'=>str_repeat('a',32),'motivation'=>'curiosidade','occupation'=>'outro','ai'=>'orientacao','interests'=>['possibilidades'],'profession'=>'','dream'=>'','website'=>''];
$clean=VisitorProfile::validate($sample);check($clean!==null);
check(str_contains(VisitorProfile::body($clean),'Curiosidade ou hobby'));
foreach(['ai','occupation','motivation'] as $key){$bad=$sample;$bad[$key]='invalido';check(VisitorProfile::validate($bad)===null);}
$bad=$sample;$bad['interests']=[];check(VisitorProfile::validate($bad)===null);
$bad=$sample;$bad['interests']=[['invalid']];check(VisitorProfile::validate($bad)===null);
$bad=$sample;$bad['dream']=str_repeat('a',2401);check(VisitorProfile::validate($bad)===null);
$bad=$sample;$bad['website']='spam';check(VisitorProfile::validate($bad)===null);
$bad=$sample;$bad['request_id']='invalid';check(VisitorProfile::validate($bad)===null);
$bad=$sample;$bad['dream']="hello\0";check(VisitorProfile::validate($bad)===null);
echo "Visitor profile validation passed\n";
