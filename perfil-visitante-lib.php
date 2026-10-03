<?php
declare(strict_types=1);

final class VisitorProfile {
    public const SCHEMA = 'CREATE TABLE IF NOT EXISTS visitor_profiles (
        request_id CHAR(32) PRIMARY KEY,
        payload TEXT NOT NULL,
        state VARCHAR(12) NOT NULL DEFAULT "queued",
        attempts INT NOT NULL DEFAULT 0,
        available BIGINT NOT NULL,
        created BIGINT NOT NULL,
        sent BIGINT NULL,
        INDEX visitor_profile_queue(state, available)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4';

    public static function ready(array $config): bool {
        return ($config['visitor_survey_enabled'] ?? true) === true;
    }

    public static function deliveryReady(array $config): bool {
        return ($config['visitor_survey_email_enabled'] ?? false) === true
            && is_string($config['visitor_survey_recipient'] ?? null)
            && (bool)filter_var($config['visitor_survey_recipient'], FILTER_VALIDATE_EMAIL)
            && !empty($config['smtp_host'])
            && (bool)filter_var($config['smtp_from'] ?? '', FILTER_VALIDATE_EMAIL);
    }

    public static function validate(array $data): ?array {
        $choices = [
            'motivation' => ['curiosidade', 'trabalho', 'negocio'],
            'occupation' => ['empresa', 'empreendedor', 'autonomo', 'estudante', 'outro'],
            'ai' => ['chatgpt', 'claude', 'gemini', 'outra', 'orientacao'],
        ];
        if (!is_string($data['request_id'] ?? null) || !preg_match('/^[a-f0-9]{32}$/D', $data['request_id'])) return null;
        $clean = ['request_id' => $data['request_id']];
        foreach ($choices as $key => $allowed) {
            if (!is_string($data[$key] ?? null) || !in_array($data[$key], $allowed, true)) return null;
            $clean[$key] = $data[$key];
        }
        $interests = $data['interests'] ?? null;
        $allowed = ['dia_a_dia', 'conteudo', 'indicadores', 'automacao', 'sistemas', 'possibilidades'];
        if (!is_array($interests) || !array_is_list($interests) || count($interests) < 1 || count($interests) > 6) return null;
        foreach ($interests as $value) if (!is_string($value) || !in_array($value, $allowed, true)) return null;
        $clean['interests'] = array_values(array_unique($interests));
        foreach (['profession' => 480, 'dream' => 2400] as $key => $limit) {
            $value = $data[$key] ?? '';
            if (!is_string($value) || strlen($value) > $limit || preg_match('/[\x00-\x08\x0B\x0C\x0E-\x1F]/', $value)) return null;
            $clean[$key] = trim($value);
        }
        if (!is_string($data['website'] ?? '') || ($data['website'] ?? '') !== '') return null;
        return $clean;
    }

    public static function body(array $data): string {
        $labels = [
            'curiosidade'=>'Curiosidade ou hobby', 'trabalho'=>'Facilitar meu trabalho', 'negocio'=>'Criar uma solução ou melhorar meu negócio',
            'empresa'=>'Trabalho em uma empresa', 'empreendedor'=>'Empreendedor', 'autonomo'=>'Autônomo', 'estudante'=>'Estudante', 'outro'=>'Outra situação',
            'chatgpt'=>'ChatGPT', 'claude'=>'Claude', 'gemini'=>'Gemini', 'outra'=>'Outra IA', 'orientacao'=>'Ainda não sei, quero orientação',
            'dia_a_dia'=>'Usar IA no dia a dia', 'conteudo'=>'Criar conteúdos', 'indicadores'=>'Analisar dados e indicadores', 'automacao'=>'Automatizar tarefas', 'sistemas'=>'Criar sites, sistemas ou agentes', 'possibilidades'=>'Descobrir as possibilidades',
        ];
        return "Nova resposta ao formulário de perfil do visitante.\n\n"
            ."Motivo: ".$labels[$data['motivation']]."\n"
            ."Situação profissional: ".$labels[$data['occupation']]."\n"
            ."Profissão ou área: ".($data['profession'] ?: 'Não informado')."\n"
            ."IA desejada: ".$labels[$data['ai']]."\n"
            ."Interesses: ".implode(', ', array_map(fn($v)=>$labels[$v], $data['interests']))."\n"
            ."Ideia ou sonho: ".($data['dream'] ?: 'Não informado')."\n\n"
            ."Referência: ".$data['request_id']."\n"
            ."Participação voluntária para planejar as formações. Esta resposta não representa matrícula.";
    }

    public static function process(FormacaoApp $app): void {
        if (!self::deliveryReady($app->config)) return;
        $app->db->exec(self::SCHEMA);
        $jobs = $app->query('SELECT * FROM visitor_profiles WHERE state=? AND available<=? ORDER BY created LIMIT 20', ['queued', time()])->fetchAll();
        foreach ($jobs as $job) {
            try {
                $data = json_decode($job['payload'], true, 512, JSON_THROW_ON_ERROR);
                $config = $app->config;
                $mail = new PHPMailer\PHPMailer\PHPMailer(true);
                $mail->isSMTP();
                $mail->Host = $config['smtp_host'];
                $mail->Port = (int)($config['smtp_port'] ?? 587);
                $mail->Timeout = 15;
                $mail->SMTPSecure = $mail->Port === 465 ? PHPMailer\PHPMailer\PHPMailer::ENCRYPTION_SMTPS : PHPMailer\PHPMailer\PHPMailer::ENCRYPTION_STARTTLS;
                $mail->SMTPAuth = !empty($config['smtp_user']);
                $mail->Username = $config['smtp_user'] ?? '';
                $mail->Password = $config['smtp_password'] ?? '';
                $mail->SMTPOptions = ['ssl'=>['verify_peer'=>true,'verify_peer_name'=>true,'allow_self_signed'=>false]];
                $mail->CharSet = 'UTF-8';
                $mail->setFrom($config['smtp_from'], 'Luís Fernando · Formação IA');
                $mail->addAddress($config['visitor_survey_recipient']);
                $mail->Subject = 'Novo perfil de visitante — Formação IA';
                $mail->isHTML(false);
                $mail->Body = self::body($data);
                $mail->send();
                $app->query('UPDATE visitor_profiles SET state=?,sent=? WHERE request_id=?', ['sent', time(), $job['request_id']]);
            } catch (Throwable) {
                $attempts = (int)$job['attempts'] + 1;
                $app->query('UPDATE visitor_profiles SET attempts=?,available=?,state=? WHERE request_id=?', [$attempts,time()+300,$attempts>=5?'failed':'queued',$job['request_id']]);
                error_log('Formacao: visitor profile delivery failed; response retained; no personal data logged');
            }
        }
    }
}
