import pathlib
from threading import Lock
from typing import ClassVar, Protocol

from transformers import AutoTokenizer


class _Tokenizer(Protocol):
    def encode(self, text: str) -> list[int]: ...


class JinaTokenizer:
    _tokenizer: ClassVar[_Tokenizer | None] = None
    _lock: ClassVar[Lock] = Lock()

    @classmethod
    def _get_tokenizer(cls) -> _Tokenizer:
        if cls._tokenizer is None:
            with cls._lock:
                if cls._tokenizer is None:
                    base_path = pathlib.Path(__file__).resolve()
                    gpt2_tokenizer_path = str(base_path.parent / "tokenizer")
                    cls._tokenizer = AutoTokenizer.from_pretrained(gpt2_tokenizer_path)
        return cls._tokenizer

    @classmethod
    def _get_num_tokens_by_jina_base(cls, text: str) -> int:
        """
        use jina tokenizer to get num tokens
        """
        tokenizer = cls._get_tokenizer()
        tokens = tokenizer.encode(text)
        return len(tokens)

    @classmethod
    def get_num_tokens(cls, text: str) -> int:
        return cls._get_num_tokens_by_jina_base(text)
