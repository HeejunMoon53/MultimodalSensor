%% plot_realtime_EI.m
% realtime_EI_*.csv 데이터를 읽어 두 개의 그래프를 그린다.
%   Figure 1: 시간에 따른 인덕턴스 변화율(dL_pct), 저항 변화율(dR_pct)
%   Figure 2: 시간에 따른 인장변형률(추정/실제), 근접도(추정/실제)
%
% CSV 컬럼:
%   t_s, dL_pct, dR_pct, dV, xa_mm, z_mm,
%   eps_ei_pct, d_ei_mm, eps_act_pct, d_act_mm, latency_us

clear; clc; close all;

%% 데이터 로드
csvFile = fullfile(fileparts(mfilename('fullpath')), 'realtime_EI_20260601_161314.csv');
data = readtable(csvFile);

%% 다운샘플링 (데이터가 너무 많아 플로팅이 느릴 때)
maxPoints = 5000;   % 그래프에 표시할 최대 포인트 수 (필요에 따라 조절)
n = height(data);
if n > maxPoints
    step = ceil(n / maxPoints);
    data = data(1:step:end, :);
    fprintf('다운샘플링 적용: %d -> %d 포인트 (step=%d)\n', n, height(data), step);
end

t       = data.t_s;
dL      = data.dL_pct;
dR      = data.dR_pct;
eps_est = data.eps_ei_pct;   % 인장변형률 추정값
eps_act = data.eps_act_pct;  % 인장변형률 실제값
d_est   = data.d_ei_mm;      % 근접도 추정값
d_act   = data.d_act_mm;     % 근접도 실제값

% 시간 원점 정렬 (선택 사항)
t = t - t(1);

%% 색상 정의
% 프로젝트 컨벤션 (CLAUDE.md 그래프 색상 컨벤션)
COLOR_L = "#FF8C00";   % 인덕턴스 L — 주황
COLOR_R = "#2CA02C";   % DC 저항 R  — 초록

% 파스텔톤 (Figure 2용)
COLOR_STRAIN = "#7FB2E5";   % 인장변형률 — 파스텔 블루
COLOR_PROX   = "#E88A8A";   % 근접도     — 파스텔 레드

%% Figure 1: dL, dR vs Time
fig1 = figure('Name', 'Inductance & Resistance Change', 'Color', 'w', 'Renderer', 'painters');
hold on;
plot(t, dL, 'Color', COLOR_L, 'LineWidth', 1.6, 'DisplayName', '\DeltaL (%)');
plot(t, dR, 'Color', COLOR_R, 'LineWidth', 1.6, 'DisplayName', '\DeltaR (%)');
hold off;

xlabel('Time (s)');
ylabel('Change (%)');
title('Inductance & Resistance Change vs Time');
legend('show', 'Location', 'best');
grid on;
box on;
drawnow;
print(fig1, fullfile(fileparts(mfilename('fullpath')), 'fig1_inductance_resistance.png'), '-dpng', '-r150');

%% Figure 2: Strain / Proximity - Estimated vs Actual
fig2 = figure('Name', 'Strain & Proximity: Estimated vs Actual', 'Color', 'w', 'Renderer', 'painters');

yyaxis left
hold on;
plot(t, eps_est, '-',  'Color', COLOR_STRAIN, 'LineWidth', 1.6, 'DisplayName', 'Strain estimated');
plot(t, eps_act, '--', 'Color', COLOR_STRAIN, 'LineWidth', 1.6, 'DisplayName', 'Strain actual');
ylabel('Strain (%)');
ax = gca;
ax.YColor = COLOR_STRAIN;
hold off;

yyaxis right
hold on;
plot(t, d_est, '-',  'Color', COLOR_PROX, 'LineWidth', 1.6, 'DisplayName', 'Proximity estimated');
plot(t, d_act, '--', 'Color', COLOR_PROX, 'LineWidth', 1.6, 'DisplayName', 'Proximity actual');
ylabel('Proximity (mm)');
ax = gca;
ax.YColor = COLOR_PROX;
hold off;

xlabel('Time (s)');
title('Strain & Proximity: Estimated vs Actual');
legend('show', 'Location', 'best');
grid on;
box on;
drawnow;
print(fig2, fullfile(fileparts(mfilename('fullpath')), 'fig2_strain_proximity.png'), '-dpng', '-r150');

fprintf('완료: fig1_inductance_resistance.png, fig2_strain_proximity.png 저장됨 (%s)\n', fileparts(mfilename('fullpath')));
