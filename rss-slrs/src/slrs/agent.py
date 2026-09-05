"""Seller agent — thin wrapper around a seller + its fleet policy.

Home for a future LLM-backed seller agent (cross-platform inventory/budget planning).
"""
from __future__ import annotations

from dataclasses import dataclass

from .sellers import Seller


@dataclass
class SellerAgent:
    seller: Seller

    def summary(self) -> dict:
        return {"seller_id": self.seller.seller_id, "n_products": len(self.seller.product_ids)}
