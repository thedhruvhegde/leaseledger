"""Advanced decision methods layered on the core engine (no change to core outputs). See README.md here.

evpi          value of (partial) information about next semester's schedule
risk          CVaR, mean-CVaR efficient set, minimax regret
tdprofile     time-dependent travel-time profile tau(t), bus cliffs, schedule flexibility
qmc           scrambled Sobol / antithetic variance reduction study
sensitivity   grouped Sobol global sensitivity indices of the #1-vs-#2 gap
elicit        Bayesian pairwise preference learning (Laplace posterior, D-optimal next question)
multiapt      multi-apartment rent division (apartment choice + envy-free split)
"""
from .evpi import evpi
from .risk import risk
from .sensitivity import sensitivity

__all__ = ["evpi", "risk", "sensitivity"]
