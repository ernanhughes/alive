"""ALIVE-PI-01B: governed Pi execution behind the ModelGateway seam.

Pi supplies agent execution. ALIVE keeps authority: it holds the real provider credential, decides
whether each upstream request may be forwarded, and records every outcome. See `docs/pi/`.
"""
