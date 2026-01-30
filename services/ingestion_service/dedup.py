from simhash import Simhash
import re

class DataDeduplicator:
    def __init__(self, threshold: int = 3):
        self.threshold = threshold
        self.seen_hashes = []

    def _get_features(self, s: str):
        width = 3
        s = s.lower()
        s = re.sub(r'[^\w]+', '', s)
        return [s[i:i + width] for i in range(max(len(s) - width + 1, 1))]

    def is_duplicate(self, content: str) -> bool:
        content_hash = Simhash(self._get_features(content)).value
        
        for existing_hash in self.seen_hashes:
            # hamming distance
            distance = bin(content_hash ^ existing_hash).count('1')
            if distance <= self.threshold:
                return True
        
        self.seen_hashes.append(content_hash)
        return False

# Singleton
deduplicator = DataDeduplicator()
