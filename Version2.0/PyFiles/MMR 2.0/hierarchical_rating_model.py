"""
Hierarchical MAP Rating Model
-----------------------------

This script implements a hierarchical Bayesian (Normal-Normal) model
to estimate player ratings relative to their leagues, while accounting
for league strength differences.

Model:
    y_i ~ Normal(theta_i, sigma_obs)
    theta_i ~ Normal(mu_g[i], sigma_player)
    mu_g ~ Normal(mu_global, sigma_league)

You get:
  - Player MAP estimates (theta_map)
  - League MAP estimates (mu_map)
  - Approximate uncertainties (Laplace)
"""

import numpy as np
import pandas as pd

try:
    from scipy import linalg
except Exception:
    linalg = None


def fit_hierarchical_map(y, league_idx, mu_global=1500.0,
                         sigma_obs=50.0, sigma_player=200.0, sigma_league=100.0):
    """
    Fit MAP estimates for the hierarchical model:
        y_i ~ Normal(theta_i, sigma_obs)
        theta_i ~ Normal(mu_g[i], sigma_player)
        mu_g ~ Normal(mu_global, sigma_league)

    Returns:
        {
            'theta_map', 'theta_std', 'mu_map', 'mu_std',
            'mu_map_by_label', 'mu_std_by_label', 'Hessian', 'Cov'
        }
    """
    y = np.asarray(y, dtype=float)
    league_idx = np.asarray(league_idx, dtype=int)
    N = len(y)
    leagues = np.unique(league_idx)
    G = len(leagues)

    # Map league labels to 0..G-1
    league_map = {old: new for new, old in enumerate(leagues)}
    league_idx_mapped = np.array([league_map[l] for l in league_idx], dtype=int)

    n_g = np.bincount(league_idx_mapped, minlength=G)
    players_in_league = [np.where(league_idx_mapped == g)[0] for g in range(G)]

    # Precisions (1 / variance)
    p_obs = 1.0 / (sigma_obs ** 2)
    p_player = 1.0 / (sigma_player ** 2)
    p_league = 1.0 / (sigma_league ** 2)

    size = N + G
    A = np.zeros((size, size), dtype=float)
    b = np.zeros(size, dtype=float)

    # Player equations
    for i in range(N):
        g = league_idx_mapped[i]
        A[i, i] = p_obs + p_player
        A[i, N + g] = -p_player
        b[i] = p_obs * y[i]

    # League equations
    for g in range(G):
        rows = players_in_league[g]
        for i in rows:
            A[N + g, i] = -p_player
        A[N + g, N + g] = n_g[g] * p_player + p_league
        b[N + g] = p_league * mu_global

    # Solve
    if linalg is not None:
        sol = linalg.solve(A, b, assume_a='pos')
    else:
        sol = np.linalg.solve(A, b)

    theta_map = sol[:N]
    mu_map = sol[N:]

    Hessian = A.copy()
    try:
        cov = linalg.inv(Hessian) if linalg else np.linalg.inv(Hessian)
    except Exception:
        cov = np.linalg.pinv(Hessian)
        print("Warning: Hessian inversion failed, used pseudo-inverse.")

    stds = np.sqrt(np.maximum(np.diag(cov), 1e-12))
    theta_std = stds[:N]
    mu_std = stds[N:]

    inv_league_map = {v: k for k, v in league_map.items()}
    mu_map_by_label = {inv_league_map[g]: mu_map[g] for g in range(G)}
    mu_std_by_label = {inv_league_map[g]: mu_std[g] for g in range(G)}

    return {
        "theta_map": theta_map,
        "theta_std": theta_std,
        "mu_map": mu_map,
        "mu_std": mu_std,
        "mu_map_by_label": mu_map_by_label,
        "mu_std_by_label": mu_std_by_label,
        "Hessian": Hessian,
        "Cov": cov
    }


# ------------------------------------------------------------
# DEMO with synthetic data
# ------------------------------------------------------------
if __name__ == "__main__":
    np.random.seed(1)

    G = 5  # leagues
    players_per_league = [80, 150, 50, 120, 30]
    N = sum(players_per_league)

    mu_global_true = 1500.0
    sigma_league_true = 100.0
    sigma_player_true = 200.0
    sigma_obs_true = 50.0

    true_mu_league = np.random.normal(mu_global_true, sigma_league_true, size=G)
    true_theta = np.empty(N)
    league_idx = np.empty(N, dtype=int)

    ptr = 0
    for g in range(G):
        n = players_per_league[g]
        true_theta[ptr:ptr+n] = np.random.normal(true_mu_league[g], sigma_player_true, size=n)
        league_idx[ptr:ptr+n] = g
        ptr += n

    y = true_theta + np.random.normal(scale=sigma_obs_true, size=N)

    fit = fit_hierarchical_map(
        y, league_idx,
        mu_global=1500.0,
        sigma_obs=50.0,
        sigma_player=200.0,
        sigma_league=100.0
    )

    df = pd.DataFrame({
        "player_id": np.arange(N),
        "league": league_idx,
        "y_obs": y,
        "theta_map": fit["theta_map"],
        "theta_std": fit["theta_std"]
    })

    league_df = pd.DataFrame([
        {
            "league": g,
            "true_mu_league": true_mu_league[g],
            "mu_map": fit["mu_map_by_label"][g],
            "mu_std": fit["mu_std_by_label"][g],
            "n_players": players_per_league[g]
        }
        for g in range(G)
    ])

    df.to_csv("player_ratings.csv", index=False)
    league_df.to_csv("league_ratings.csv", index=False)

    print("Saved:")
    print("  player_ratings.csv")
    print("  league_ratings.csv")
    print("\nTop 5 leagues by μ:")
    print(league_df.sort_values("mu_map", ascending=False).head())
