-- ============================================================
-- pvSolar - inicializacao do PostgreSQL (docker-entrypoint-initdb.d)
-- Executado automaticamente APENAS na primeira subida (volume vazio).
--
-- Bancos do ecossistema:
--   pvsolar_auth          -> servico de autenticacao (producao)
--   pvsolar_auth_test     -> testes do auth (dropam o schema a cada run)
--   pvsolar_scheduler     -> servico de agendamento (producao)
--   pvsolar_scheduler_test-> testes do scheduler (dropam o schema)
--   pvsolar_analytics     -> SELECT 1 de partida do Analytics (init eager)
-- ============================================================

CREATE DATABASE pvsolar_auth;
CREATE DATABASE pvsolar_auth_test;
CREATE DATABASE pvsolar_scheduler;
CREATE DATABASE pvsolar_scheduler_test;
CREATE DATABASE pvsolar_analytics;
