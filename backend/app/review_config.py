"""
review_config.py
================
Constants for human review bucketing.
"""

LEAD_SCORE_THRESHOLD = 60
LEAD_AUTO_REJECT_THRESHOLD = 20

VALID_REVIEW_STATUSES = {"approved", "pending_review", "rejected"}
# freelancer/reddit removed — reclassified as active_request (high intent) sources
NOISY_SOURCES = {"truelancer"}
