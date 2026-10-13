from dataclasses import dataclass, field


@dataclass
class SessionState:
    ocr_text: str = ""
    summary: str = ""
    sentences: list = field(default_factory=list)
    sentence_index: int = 0
    words: list = field(default_factory=list)
    word_index: int = 0
    character: str = ""
    character_index: int = 0
    total_characters: int = 0
    dots: list = field(default_factory=list)
    motors: list = field(default_factory=lambda: [False] * 6)
    is_playing: bool = False

    def to_dict(self) -> dict:
        """Shape matches the sync contract: what the website shows should
        equal what the physical device is doing."""
        return {
            "ocrText": self.ocr_text,
            "summary": self.summary,
            "sentence": self.sentences[self.sentence_index] if self.sentences else "",
            "word": self.words[self.word_index] if self.words else "",
            "character": self.character,
            "characterIndex": self.character_index,
            "wordIndex": self.word_index,
            "totalCharacters": self.total_characters,
            "totalWords": len(self.words),
            "dots": self.dots,
            "motors": self.motors,
            "isPlaying": self.is_playing,
        }
