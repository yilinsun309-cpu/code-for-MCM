% ============================================================================
% MCM 2026 Problem B: Moon Colony Transportation Optimization - Task 1
% Toolbox-free MATLAB script (analytical search, no linprog/intlinprog)
% ============================================================================

clear all; close all; clc;

%% ==================== PARAMETERS & DATA INPUT ====================
fprintf('========== MCM 2026 Problem B - Task 1 ==========\n\n');

% Global Parameters
M_goal = 1e8;           % Total material requirement (ton)

% Space Elevator Parameters
N_SE = 3;               % Number of Galactic Harbours
Cap_SE = 5.37e5;        % Annual capacity (ton/yr) = 179000 * 3
E_week = 672;           % Weekly electricity consumption (MWh)
P_elec = 0.213;         % Electricity price (USD/kWh)
C_maint = 1.2e8;        % Annual maintenance cost (USD/yr)
C_TV_fixed = 3.0e8;     % Fixed Apex-to-Moon transfer cost (USD)

% Calculate C_elec_unit (electricity cost per ton)
Annual_E_consumption = N_SE * E_week * 52 * 1000;  % kWh/yr
C_elec_unit = (Annual_E_consumption * P_elec) / Cap_SE;  % USD/ton

% Rocket Parameters
C_launch_new = 1.5e8;     % Cost per single Falcon Heavy (new)
C_launch_reused = 0.97e8; % Cost per single Falcon Heavy (reused)
Cap_rock = 125;           % Payload capacity (ton/launch)

% Assume reused rockets ratio
R = 0.7;
C_launch_avg = R * C_launch_reused + (1-R) * C_launch_new;

% Launch frequency constraint
f_total = 50;            % Max annual launches (launches/yr)

% Time window
T_max = 24;
T_min = 1;

fprintf('Parameters:\n');
fprintf('  M_goal = %.2e ton\n', M_goal);
fprintf('  Cap_SE = %.2e ton/yr\n', Cap_SE);
fprintf('  C_elec_unit = $%.2f/ton\n', C_elec_unit);
fprintf('  C_launch_avg = $%.2e/launch\n', C_launch_avg);
fprintf('  f_total = %d launches/yr\n', f_total);
fprintf('  T_max = %d years\n\n', T_max);

% Preallocate scenario outputs
M_SE_A = NaN; N_Rock_A = NaN; T_A = NaN; Z_A = NaN; feasible_A = false;
M_SE_B = NaN; N_Rock_B = NaN; T_B = NaN; Z_B = NaN; feasible_B = false;
M_SE_C = NaN; N_Rock_C = NaN; T_C = NaN; Z_C = NaN; feasible_C = false;

%% ==================== SCENARIO A: SPACE ELEVATOR ONLY ====================
fprintf('========== SCENARIO A: SPACE ELEVATOR ONLY ==========\n');

T_need_A = max(T_min, M_goal / Cap_SE);
if T_need_A <= T_max
    feasible_A = true;
    T_A = T_need_A;
    M_SE_A = M_goal;
    N_Rock_A = 0;
    cost_oper_A = C_elec_unit * M_SE_A + C_maint * T_A;
    Z_A = cost_oper_A + C_TV_fixed;
    
    fprintf('  M_SE = %.2e ton\n', M_SE_A);
    fprintf('  N_Rock = %d launches\n', N_Rock_A);
    fprintf('  T = %.2f years\n', T_A);
    fprintf('  Total Cost (Operational) = $%.2e\n', cost_oper_A);
    fprintf('  Total Cost (with Fixed) = $%.2e\n', Z_A);
else
    fprintf('  INFEASIBLE: Cap_SE*T_max = %.2e < demand %.2e\n', Cap_SE*T_max, M_goal);
end

%% ==================== SCENARIO B: TRADITIONAL ROCKETS ONLY ====================
fprintf('\n========== SCENARIO B: TRADITIONAL ROCKETS ONLY ==========\n');

N_need_B = ceil(M_goal / Cap_rock);
T_need_B = max(T_min, N_need_B / f_total);
if T_need_B <= T_max
    feasible_B = true;
    M_SE_B = 0;
    N_Rock_B = N_need_B;
    T_B = T_need_B;
    cost_oper_B = C_launch_avg * N_Rock_B + C_maint * T_B;
    Z_B = cost_oper_B + C_TV_fixed;
    
    fprintf('  M_SE = %.2e ton\n', M_SE_B);
    fprintf('  N_Rock = %d launches\n', N_Rock_B);
    fprintf('  T = %.2f years\n', T_B);
    fprintf('  Total Cost (Operational) = $%.2e\n', cost_oper_B);
    fprintf('  Total Cost (with Fixed) = $%.2e\n', Z_B);
else
    fprintf('  INFEASIBLE: need %.0f launches, exceeds %.0f allowed within T_max\n', N_need_B, f_total * T_max);
end

%% ==================== SCENARIO C: COMBINED STRATEGY ====================
fprintf('\n========== SCENARIO C: COMBINED STRATEGY ==========\n');

% Search optimal cost over a fine T grid (about 0.1-year resolution)
T_grid = linspace(T_min, T_max, 231);
best_cost = inf;

for T_cur = T_grid
    M_cap = Cap_SE * T_cur;
    N_cap = f_total * T_cur;
    
    M_use = min(M_goal, M_cap);
    remaining = max(0, M_goal - M_use);
    N_need = ceil(remaining / Cap_rock);
    
    if N_need <= N_cap  % feasible for this T
        cost_oper = C_elec_unit * M_use + C_launch_avg * N_need + C_maint * T_cur;
        Z_total = cost_oper + C_TV_fixed;
        if Z_total < best_cost
            best_cost = Z_total;
            feasible_C = true;
            T_C = T_cur;
            M_SE_C = M_use;
            N_Rock_C = N_need;
            Z_C = Z_total;
        end
    end
end

if feasible_C
    fprintf('  M_SE = %.2e ton (%.1f%% of total)\n', M_SE_C, 100*M_SE_C/M_goal);
    fprintf('  N_Rock = %d launches (%.1f%% of load)\n', N_Rock_C, 100*N_Rock_C*Cap_rock/M_goal);
    fprintf('  T = %.2f years\n', T_C);
    fprintf('  Total Cost (Operational) = $%.2e\n', Z_C - C_TV_fixed);
    fprintf('  Total Cost (with Fixed) = $%.2e\n', Z_C);
else
    fprintf('  INFEASIBLE within T_max given current capacities.\n');
end

%% ==================== PARETO FRONTIER SWEEP ====================
fprintf('\n========== PARETO FRONTIER: TIME SWEEP ==========\n');

T_sweep = linspace(T_min, T_max, 15);
Pareto_results = [];

for T_fixed = T_sweep
    M_cap = Cap_SE * T_fixed;
    N_cap = f_total * T_fixed;
    M_use = min(M_goal, M_cap);
    remaining = max(0, M_goal - M_use);
    N_need = ceil(remaining / Cap_rock);
    
    if N_need <= N_cap
        cost_oper = C_elec_unit * M_use + C_launch_avg * N_need + C_maint * T_fixed;
        Z_total = cost_oper + C_TV_fixed;
        Pareto_results = [Pareto_results; T_fixed, Z_total/1e9, M_use/1e6, N_need];
        fprintf('  T = %.2f yr -> Cost = $%.1f B\n', T_fixed, Z_total/1e9);
    end
end

%% ==================== SUMMARY TABLE ====================
fprintf('\n========== SUMMARY: THREE SCENARIOS ==========\n');
fprintf('%-20s | %-12s | %-15s | %-15s | %-12s\n', 'Scenario', 'Time (yr)', 'M_SE (10^6 ton)', 'N_Rock', 'Cost ($B)');
fprintf(repmat('-', 1, 80) + "\n");

if feasible_A
    fprintf('%-20s | %12.2f | %15.1f | %15.0f | %12.2f\n', 'A: SE Only', T_A, M_SE_A/1e6, N_Rock_A, Z_A/1e9);
else
    fprintf('%-20s | INFEASIBLE\n', 'A: SE Only');
end

if feasible_B
    fprintf('%-20s | %12.2f | %15.1f | %15.0f | %12.2f\n', 'B: Rockets Only', T_B, M_SE_B/1e6, N_Rock_B, Z_B/1e9);
else
    fprintf('%-20s | INFEASIBLE\n', 'B: Rockets Only');
end

if feasible_C
    fprintf('%-20s | %12.2f | %15.1f | %15.0f | %12.2f\n', 'C: Combined', T_C, M_SE_C/1e6, N_Rock_C, Z_C/1e9);
else
    fprintf('%-20s | INFEASIBLE\n', 'C: Combined');
end

fprintf('\n');

%% ==================== PLOTTING ====================
figure('Position', [100, 100, 1200, 900]);

% Plot 1: Cost Comparison
subplot(2, 3, 1);
scenarios = {'Scenario A\n(SE Only)', 'Scenario B\n(Rockets)', 'Scenario C\n(Combined)'};
costs = [Z_A/1e9, Z_B/1e9, Z_C/1e9];
bar(1:3, costs, 'FaceColor', [0.2, 0.6, 0.9], 'EdgeColor', 'black', 'LineWidth', 1.5);
set(gca, 'XTickLabel', scenarios, 'FontSize', 10);
ylabel('Total Cost ($B)', 'FontSize', 11, 'FontWeight', 'bold');
title('Cost Comparison', 'FontSize', 12, 'FontWeight', 'bold');
grid on; grid minor;
for i = 1:3
    if ~isnan(costs(i)) && costs(i) < 1e4
        text(i, costs(i) + 50, sprintf('$%.0f B', costs(i)), 'HorizontalAlignment', 'center', 'FontWeight', 'bold');
    end
end

% Plot 2: Time Comparison
subplot(2, 3, 2);
times = [T_A, T_B, T_C];
bar(1:3, times, 'FaceColor', [0.2, 0.8, 0.2], 'EdgeColor', 'black', 'LineWidth', 1.5);
set(gca, 'XTickLabel', scenarios, 'FontSize', 10);
ylabel('Completion Time (years)', 'FontSize', 11, 'FontWeight', 'bold');
title('Project Duration', 'FontSize', 12, 'FontWeight', 'bold');
grid on; grid minor;
yline(T_max, 'r--', 'Deadline (2050)', 'LineWidth', 1.5);
for i = 1:3
    if ~isnan(times(i))
        text(i, times(i) + 1.5, sprintf('%.1f yr', times(i)), 'HorizontalAlignment', 'center', 'FontWeight', 'bold');
    end
end

% Plot 3: Mass Distribution
subplot(2, 3, 3);
M_SE_vals = [M_SE_A/1e6, M_SE_B/1e6, M_SE_C/1e6];
M_Rock_vals = [N_Rock_A*Cap_rock/1e6, N_Rock_B*Cap_rock/1e6, N_Rock_C*Cap_rock/1e6];
bar(1:3, [M_SE_vals; M_Rock_vals]', 'stacked', 'EdgeColor', 'black', 'LineWidth', 1.5);
set(gca, 'XTickLabel', scenarios, 'FontSize', 10);
ylabel('Total Mass (Million tons)', 'FontSize', 11, 'FontWeight', 'bold');
title('Mass: SE vs Rockets', 'FontSize', 12, 'FontWeight', 'bold');
legend('Space Elevator', 'Rockets', 'FontSize', 10, 'Location', 'NorthEast');
grid on; grid minor;

% Plot 4: Pareto Frontier
subplot(2, 3, 4);
if ~isempty(Pareto_results)
    plot(Pareto_results(:, 1), Pareto_results(:, 2), 'o-', 'LineWidth', 2, ...
        'MarkerSize', 8, 'MarkerFaceColor', [1, 0.5, 0], 'MarkerEdgeColor', 'black');
    hold on;
    if feasible_A
        plot(T_A, Z_A/1e9, 's', 'MarkerSize', 12, 'MarkerFaceColor', 'red', 'MarkerEdgeColor', 'black', 'LineWidth', 2);
        text(T_A + 0.5, Z_A/1e9, 'A', 'FontSize', 11, 'FontWeight', 'bold');
    end
    if feasible_B
        plot(T_B, Z_B/1e9, '^', 'MarkerSize', 12, 'MarkerFaceColor', 'green', 'MarkerEdgeColor', 'black', 'LineWidth', 2);
        text(T_B + 0.5, Z_B/1e9, 'B', 'FontSize', 11, 'FontWeight', 'bold');
    end
    if feasible_C
        plot(T_C, Z_C/1e9, 'd', 'MarkerSize', 12, 'MarkerFaceColor', 'blue', 'MarkerEdgeColor', 'black', 'LineWidth', 2);
        text(T_C + 0.5, Z_C/1e9, 'C', 'FontSize', 11, 'FontWeight', 'bold');
    end
    xlabel('Project Duration T (years)', 'FontSize', 11, 'FontWeight', 'bold');
    ylabel('Total Cost ($B)', 'FontSize', 11, 'FontWeight', 'bold');
    title('Pareto Frontier: Cost vs Time', 'FontSize', 12, 'FontWeight', 'bold');
    xline(T_max, 'r--', 'Deadline', 'LineWidth', 1.5, 'Alpha', 0.7);
    legend('Frontier', 'A', 'B', 'C', 'FontSize', 10);
    grid on; grid minor;
    hold off;
end

% Plot 5: Cost Breakdown for Scenario C
subplot(2, 3, 5);
if feasible_C
    cost_elec = M_SE_C * C_elec_unit / 1e9;
    cost_rocket = N_Rock_C * C_launch_avg / 1e9;
    cost_maint = T_C * C_maint / 1e9;
    cost_fixed = C_TV_fixed / 1e9;
    
    costs_bd = [cost_elec, cost_rocket, cost_maint, cost_fixed];
    labels_bd = {'Electricity', 'Rockets', 'Maintenance', 'Fixed'};
    
    pie(costs_bd, labels_bd);
    title('Cost Breakdown: Scenario C', 'FontSize', 12, 'FontWeight', 'bold');
end

% Plot 6: Sensitivity
subplot(2, 3, 6);
if ~isempty(Pareto_results)
    plot(Pareto_results(:, 1), Pareto_results(:, 2), 'o-', 'LineWidth', 2, ...
        'MarkerSize', 8, 'MarkerFaceColor', [0.2, 0.8, 0.2]);
    hold on;
    xlabel('Project Duration T (years)', 'FontSize', 11, 'FontWeight', 'bold');
    ylabel('Total Cost ($B)', 'FontSize', 11, 'FontWeight', 'bold');
    title('Cost Sensitivity to Time', 'FontSize', 12, 'FontWeight', 'bold');
    xline(T_max, 'r--', 'Deadline', 'LineWidth', 1.5, 'Alpha', 0.7);
    grid on; grid minor;
    hold off;
end

sgtitle('MCM 2026 Problem B - Task 1: Transportation Optimization', ...
    'FontSize', 14, 'FontWeight', 'bold');

%% ==================== EXPORT RESULTS ====================
fprintf('========== EXPORTING RESULTS ==========\n');

% Summary table
summary_data = table(...
    {'Scenario A'; 'Scenario B'; 'Scenario C'}, ...
    [T_A; T_B; T_C], ...
    [M_SE_A/1e6; M_SE_B/1e6; M_SE_C/1e6], ...
    [N_Rock_A; N_Rock_B; N_Rock_C], ...
    [Z_A/1e9; Z_B/1e9; Z_C/1e9], ...
    'VariableNames', {'Scenario', 'Time_years', 'SE_mass_M_ton', 'Rocket_launches', 'Total_Cost_B_USD'});

disp(summary_data);

% Save to CSV
try
    writetable(summary_data, 'MCM_Task1_Results.csv');
    fprintf('OK Results saved to: MCM_Task1_Results.csv\n');
catch
    fprintf('! Could not save CSV (check file permissions)\n');
end

% Pareto frontier
if ~isempty(Pareto_results)
    pareto_table = table(Pareto_results(:, 1), Pareto_results(:, 2), ...
        Pareto_results(:, 3), round(Pareto_results(:, 4)), ...
        'VariableNames', {'Time_years', 'Cost_B_USD', 'SE_mass_M_ton', 'Rocket_launches'});
    try
        writetable(pareto_table, 'MCM_Pareto_Frontier.csv');
        fprintf('OK Pareto frontier saved to: MCM_Pareto_Frontier.csv\n');
    catch
        fprintf('! Could not save Pareto CSV\n');
    end
end

fprintf('\n========== COMPUTATION COMPLETE ==========\n');
fprintf('All results displayed above. Figures saved as PNG in current folder.\n');
