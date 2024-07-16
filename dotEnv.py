"""本模块用于.env解析"""

from typing import Any, List, Dict, Union
from enum import Enum
import json
import os

class Token(Enum):
    EQUAL = "="
    LBRACKETS = "["
    RBRACKETS = "]"
    DOUBLE_QUOTE = '"'
    LBRACES = "{"
    RBRACES = "}"
    LGROUP = "("
    RAW = "`"
    RGROUP = ")"
    SINGLE_QUOTE = "'"
    Colon = ":"
    COMMAS = ","
    HASH = "#"


class Stack:
    stack = 0
    __push__ = ["{", "[", "(", "<"]
    __pop__ = ["}", "]", ")", ">"]

    def push(self, ch):
        if ch in self.__push__:
            self.stack += 1

    def pop(self, ch):
        if ch in self.__push__:
            self.stack -= 1

    def balance(self):
        return self.stack == 0


class EnvToken:
    kind: "TokenKind"
    value: str

    def __init__(self, kind: "TokenKind", value: str) -> None:
        self.kind = kind
        self.value = value


class TokenKind(Enum):
    Text = "text"
    Number = "number"
    ENV = "env"
    Equal = "equal"
    Comment = "comment"
    Commas = "commas"
    Array = "array"
    JSON = "json"
    Tuple = "tuple"
    Brackets = "brackets"
    EOF = "eof"
    Hash = "hash"


def is_numeric(ch):
    return "0" <= ch <= "9"


def is_letter(ch):
    return ("a" <= ch <= "z") or ("A" <= ch <= "Z") or ch >= "\xff"


def is_whitespace(ch):
    return ch == "\n" or ch == " " or ch == "\r" or ch == "\t"


class DotENV:
    content: str = ""
    current: int = 0
    maxLength: int = 0
    env: Dict[str, Any] = {}
    delimiter = "_"
    tokens: List[EnvToken] = []

    def __init__(self, text: str,delimiter="_") -> None:
        self.delimiter = delimiter
        self.__parser__(self.__tokenize__(text))

    def __tokenize__(self, text: str):
        tokens: List[EnvToken] = []
        self.content = text
        self.maxLength = len(text)
        current = 0
        length = len(text)
        while current < length:
            ch = text[current]
            if is_numeric(ch):
                tokens.append(self.__parser_number__(current))
                current = self.current
            elif is_letter(ch):
                tokens.append(self.__parser_key__(current))
                current = self.current
            elif ch == Token.HASH.value:
                tokens.append(EnvToken(TokenKind.Hash, ch))
                current += 1
                tokens.append(self.__parser_comment__(current))
                current = self.current
            elif ch == '"' or ch == "'":
                # process string
                tokens.append(self.__parser_string__(ch, current=current))
                current = self.current
            elif ch == Token.RAW.value:
                tokens.append(self.__parser_raw_string__(current))
                current = self.current
            elif ch == Token.LBRACKETS.value or ch == Token.RBRACKETS.value:
                # process [ and ]
                tokens.append(EnvToken(TokenKind.Brackets, ch))
                current += 1
            elif ch == Token.LBRACES.value:
                tokens.append(self.__parser_json__(current))
                current = self.current
            elif ch == Token.COMMAS.value:
                # process ,
                tokens.append(EnvToken(TokenKind.Commas, ch))
                current += 1
            elif ch == Token.EQUAL.value:
                # process =
                tokens.append(EnvToken(TokenKind.Equal, ch))
                current += 1
            elif is_whitespace(ch):
                current += 1
            else:
                current += 1
        self.tokens = tokens
        return self.tokens

    def __parser_string__(self, entry: str, current: int):
        self.current = current
        self.current += 1
        ch = self.content[self.current]
        value = ""
        while self.current < self.maxLength and ch != entry:
            value = value + ch
            self.current += 1
            ch = self.content[self.current]
        self.current += 1
        return EnvToken(TokenKind.Text, value=value)

    def __parser__(self, tokens: List[EnvToken]):
        if not tokens:
            return
        current = 0
        maxTokenLength = len(tokens)
        token_cache: List[EnvToken] = []
        name = ""
        while current < maxTokenLength:
            current_token = tokens[current]
            if current_token.kind == TokenKind.ENV:
                token_cache.append(current_token)
            elif current_token.kind == TokenKind.Brackets:
                current += 1
                if current >= maxTokenLength:
                    break
                current_token = tokens[current]
                value = []
                while (
                    current < maxTokenLength
                    and current_token.kind != TokenKind.Brackets
                ):
                    if current_token.kind == TokenKind.Number:
                        value.append(float(current_token.value))
                    elif current_token.kind == TokenKind.Commas:
                        current += 1
                        if current >= maxTokenLength:
                            break
                        current_token = tokens[current]
                        continue
                    else:
                        value.append(current_token.value)
                    current += 1
                    if current < maxTokenLength:
                        current_token = tokens[current]
                if name:
                    self.env[name] = value
                    name = ""
            elif current_token.kind == TokenKind.Equal:
                if token_cache:
                    name = token_cache.pop().value
            elif current_token.kind == TokenKind.Number:
                if name:
                    self.env[name] = float(current_token.value)
                    name = ""  # Reset name after setting the value
            elif current_token.kind == TokenKind.Text:
                if name:
                    self.env[name] = current_token.value
                    name = ""  # Reset name after setting the value
            elif current_token.kind == TokenKind.JSON:
                if name:
                    self.env[name] = json.loads(current_token.value)
                    name = ""  # Reset name after setting the value
            current += 1

    def __parser_key__(self, current: int):
        self.current = current
        value = ""
        ch = self.content[self.current]
        while self.current < self.maxLength and (ch.isalpha() or ch.isdigit()):
            value += ch
            self.current += 1
            if self.current < self.maxLength:
                ch = self.content[self.current]
        return EnvToken(TokenKind.ENV, value=value)

    def __parser_number__(self, current: int):
        self.current = current
        ch = self.content[self.current]
        value = ""
        dot = 0
        while self.current < self.maxLength and (is_numeric(ch) or ch == "."):
            value = value + ch
            if ch == ".":
                dot += 1
            self.current += 1
            if self.current < self.maxLength:
                ch = self.content[self.current]

        if dot > 1:
            return EnvToken(TokenKind.Text, value=value)
        return EnvToken(TokenKind.Number, value=value)

    def __parser_raw_string__(self, current: int):
        self.current = current + 1
        value = ""
        ch = self.content[self.current]
        while self.current < self.maxLength and ch != Token.RAW.value:
            value += ch
            self.current += 1
            if self.current < self.maxLength:
                ch = self.content[self.current]
        self.current += 1
        return EnvToken(TokenKind.Text, value=value)

    def __parser_comment__(self, current: int):
        self.current = current
        value = ""
        ch = self.content[self.current]
        while self.current < self.maxLength and ch != "\n":
            value += ch
            self.current += 1
            if self.current < self.maxLength:
                ch = self.content[self.current]
        return EnvToken(TokenKind.Comment, value=value)

    def __parser_json__(self, current: int):
        self.current = current
        stack = Stack()
        ch = self.content[self.current]
        value = ""
        while self.current < self.maxLength:
            value += ch
            if ch == Token.LBRACES.value:
                stack.push(ch)
            if ch == Token.RBRACES.value:
                stack.pop(ch)
            if stack.balance():
                break
            self.current += 1
            if self.current < self.maxLength:
                ch = self.content[self.current]
        self.current += 1
        return EnvToken(TokenKind.JSON, value=value)

    def __str__(self) -> str:
        text = []
        for key in self.env:
            if isinstance(self.env[key],dict):
                temp = {}
                temp[key] = self.env[key]
                self.flatten_nested_dict(temp)
                for flatten_key in temp:
                    text.append("=".join([
                        flatten_key,
                        temp[flatten_key]
                    ]))
            else:
                text.append(
                    "=".join(
                        [
                            key,
                            self.env.get(key),  # type: ignore
                        ]
                    )
                )
        return "\n".join(text)

    def __getitem__(self, name: str) -> Any:
        return self.env[name]

    def __setitem__(self, name: str, value: Any) -> None:
        self.env[name] = value
    
    def __nest__(self,key,value):
        keys = key.split(self.delimiter)
        nested_obj = current_level = {}
        for key_ in keys[:-1]:
            current_level[key_] = {}
            current_level = current_level[key_]
        current_level[keys[-1]] = value
        return nested_obj
    
    def flatten_nested_dict(self,obj:Union[Dict[str,Any],List[Any]], parent_key='')->Dict[str,str]:
        items = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                new_key = f'{parent_key}{self.delimiter}{k}' if parent_key else k
                items.extend(self.flatten_nested_dict(v, new_key).items())
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                new_key = f'{parent_key}{self.delimiter}{i}' if parent_key else str(i)
                items.extend(self.flatten_nested_dict(v, new_key).items())
        else:
            items.append((parent_key, obj))
        return dict(items)
    
    def environment(self):
        env = self.flatten_nested_dict(self.env)
        for key in env:
            os.environ[key] = env[key]