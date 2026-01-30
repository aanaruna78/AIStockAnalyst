from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from textblob import TextBlob
from typing import Dict

class SentimentAnalyzer:
    def __init__(self):
        self.vader = SentimentIntensityAnalyzer()

    def analyze(self, text: str) -> Dict[str, float]:
        # VADER analysis (Good for social media, slag, capitalization)
        vader_scores = self.vader.polarity_scores(text)
        
        # TextBlob analysis (Good for subjectivity)
        blob = TextBlob(text)
        
        return {
            "polarity": vader_scores['compound'],         # -1.0 to 1.0
            "subjectivity": blob.sentiment.subjectivity,  # 0.0 to 1.0
            "pos": vader_scores['pos'],
            "neg": vader_scores['neg'],
            "neu": vader_scores['neu']
        }

# Singleton
sentiment_analyzer = SentimentAnalyzer()
