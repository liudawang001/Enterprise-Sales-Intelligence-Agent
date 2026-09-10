from typing import Protocol

try:
    import jieba
except ImportError:  # pragma: no cover
    jieba = None


class LexicalTokenizer(Protocol):
    def tokenize(self, text: str) -> str:
        ...


class JiebaLexicalTokenizer:
    def tokenize(self, text: str) -> str:
        if jieba is None:
            return " ".join(text)
        return " ".join(token.strip() for token in jieba.cut(text, cut_all=False) if token.strip())
