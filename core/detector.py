from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

import pandas as pd
from rapidfuzz import fuzz


MANDATORY_PARAMS = ["po_number", "vendor_name"]
OPTIONAL_PARAMS = ["line_item", "item_description", "doc_date"]


@dataclass
class DetectedParameter:
    parameter: str
    confidence: str
    present_in: List[str]
    sample_values: List[str]


class ParameterDetector:
    """
    Analyses the three standardised DataFrames and suggests matching
    parameters with confidence levels.
    """

    def __init__(self, fuzzy_threshold: int = 85) -> None:
        self.fuzzy_threshold = fuzzy_threshold

    def detect(
        self,
        df_po: pd.DataFrame,
        df_grn: pd.DataFrame,
        df_inv: pd.DataFrame,
    ) -> List[Dict]:
        docs = {
            "PO": df_po,
            "GRN": df_grn,
            "INV": df_inv,
        }

        cols_by_doc: Dict[str, List[str]] = {
            name: [str(c) for c in df.columns] for name, df in docs.items()
        }

        all_params: List[str] = list(dict.fromkeys(MANDATORY_PARAMS + OPTIONAL_PARAMS))

        suggestions: List[DetectedParameter] = []

        for param in all_params:
            present_in = [doc for doc, cols in cols_by_doc.items() if param in cols]
            score = len(present_in)

            # Fuzzy support – look for very similar names across docs
            if score < 2:
                similar_count = self._fuzzy_presence(param, cols_by_doc.values())
                if similar_count >= 2 and score == 0:
                    score = 1  # fuzzy only

            confidence = self._score_to_confidence(param, score)
            sample_values = self._sample_values(param, docs)

            # Ensure mandatory params are always suggested, even if absent
            if param in MANDATORY_PARAMS or score > 0 or confidence != "LOW":
                suggestions.append(
                    DetectedParameter(
                        parameter=param,
                        confidence=confidence,
                        present_in=present_in,
                        sample_values=sample_values,
                    )
                )

        # Rank: mandatory first, then by confidence, then by name
        def _rank_key(p: DetectedParameter):
            conf_rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(p.confidence, 0)
            mandatory_rank = 1 if p.parameter in MANDATORY_PARAMS else 0
            return (-mandatory_rank, -conf_rank, p.parameter)

        suggestions.sort(key=_rank_key)

        return [
            {
                "parameter": s.parameter,
                "confidence": s.confidence,
                "present_in": s.present_in,
                "sample_values": s.sample_values,
            }
            for s in suggestions
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _fuzzy_presence(
        self, target: str, cols_by_docs: Sequence[Sequence[str]]
    ) -> int:
        """
        Counts in how many docs we have a column that is fuzzily similar
        to the target name.
        """
        count = 0
        for cols in cols_by_docs:
            best = 0
            for c in cols:
                score = fuzz.token_sort_ratio(target.lower(), str(c).lower())
                if score > best:
                    best = score
            if best >= self.fuzzy_threshold:
                count += 1
        return count

    @staticmethod
    def _score_to_confidence(param: str, score: int) -> str:
        if score >= 3:
            return "HIGH"
        if score == 2:
            return "HIGH" if param in MANDATORY_PARAMS else "MEDIUM"
        if score == 1:
            return "LOW"
        return "LOW"

    @staticmethod
    def _sample_values(
        param: str,
        docs: Dict[str, pd.DataFrame],
        max_samples: int = 5,
    ) -> List[str]:
        values = []
        for name in ["PO", "GRN", "INV"]:
            df = docs[name]
            if param in df.columns:
                series = df[param].dropna().astype(str).head(max_samples)
                values.extend(series.tolist())
            if values:
                break
        return values

