<?php
// Copie como config.php DENTRO de formacao-private, acima de public_html.
// Nunca publique esse arquivo com credenciais reais no GitHub.
return [
    'origin' => 'https://luisfernando.online',
    'db_host' => 'localhost',
    'db_port' => 3306,
    'db_name' => 'SUBSTITUA_PELO_NOME_COMPLETO_DO_BANCO',
    'db_user' => 'SUBSTITUA_PELO_USUARIO_COMPLETO',
    'db_password' => 'SUBSTITUA_LOCALMENTE',
    // Chave única de instalação: gere pelo menos 32 caracteres aleatórios.
    // O instalador apaga esta chave após criar a conta do professor.
    'setup_key' => 'SUBSTITUA_POR_32_CARACTERES_ALEATORIOS_OU_MAIS',
    'admin_totp_secret' => 'SUBSTITUA_PELA_CHAVE_BASE32_GERADA_LOCALMENTE',
    'allow_http' => false,
    // SMTP opcional; sem ele, o professor compartilha links pelo painel.
    // Formulário grava no banco sem SMTP. Envio futuro é ativado separadamente.
    'visitor_survey_enabled' => true,
    'visitor_survey_email_enabled' => false,
    'visitor_survey_recipient' => '',
    'smtp_host' => '',
    'smtp_port' => 587,
    'smtp_user' => '',
    'smtp_password' => '',
    'smtp_from' => '',
];

