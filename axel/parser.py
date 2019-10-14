"""
    axel is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    axel is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with axel.  If not, see <https://www.gnu.org/licenses/>.
"""
import axel.tokens as Tokens
from collections import deque
from typing import Union, List, overload, Deque, Tuple
from axel.lexer import Lexer, Yylex
from axel.symbol import Symbol_Table, U_Int16

token_t = Union[Tokens.Lexeme, Tokens.Mnemonic, Tokens.Register]


class AssemblerParserError(Exception):
    pass


class Parser:
    def __init__(self, source: str) -> None:
        self.addressing_mode: Tokens.AddressingMode
        self.lexer: Lexer = Lexer(source)
        self.symbols: Symbol_Table = Symbol_Table()

    def _error(self,
               source: str,
               expected: str,
               found: Tokens.TokenEnum) -> None:
        raise AssemblerParserError(
            f'Parser failed near "{source}", '
            f'expected one of "{expected}", '
            f'but found "{found.name}"')

    def parse_immediate_value(self, value: str) -> bytes:
        """TODO: Decimal, binary, single character. """
        if value[:1] == '#' and value[1:2] == '$':
            return bytes.fromhex(value[2:])
        else:
            return bytes.fromhex(value[1:])

    @overload
    def take(self, test: List[token_t]) -> None: ...

    @overload
    def take(self, test: token_t) -> None: ...

    def take(self, test: Union[token_t, List[token_t]]) -> None:
        lexer = self.lexer
        next_token = next(lexer)
        location = lexer.last_addr
        error = lexer._source[location:location + 12].replace('\n', ' ')
        if isinstance(test, list):
            if next_token not in test:
                options = list(map(lambda x: x.name, test))
                lexer.retract()
                self._error(error, ','.join(options), next_token)
        else:
            if next_token is not test:
                lexer.retract()
                self._error(error, test.name, next_token)

    def line(self) -> Union[
            Tuple[Tokens.TokenEnum, Deque[Yylex]],
            bool]:
        lexer = self.lexer
        location = lexer.last_addr
        test = [
            Tokens.Lexeme.T_LABEL.name,
            Tokens.Lexeme.T_VARIABLE.name,
            Tokens.Lexeme.T_MNEMONIC.name]
        source = lexer._source[location:location + 12].replace('\n', ' ')
        try:
            next(lexer)
            current = lexer.last_token
            if current == Tokens.Lexeme.T_LABEL:
                self.label(lexer.yylex)
                self.take(list(Tokens.Mnemonic))
                return self.instruction(lexer.yylex)
            elif current == Tokens.Lexeme.T_VARIABLE:
                self.variable(lexer.yylex)
                return True
            elif isinstance(current, Tokens.Mnemonic):
                return self.instruction(lexer.yylex)
        except StopIteration:
            return False  # Done.

        # Should never get here.
        self._error(source, ', '.join(test), lexer.last_token)
        return False

    def variable(self, label: Yylex) -> None:
        name = label['data']
        addr = self.lexer.last_addr
        self.take(Tokens.Lexeme.T_EQUAL)
        self.take([Tokens.Lexeme.T_DIR_ADDR_UINT8,
                   Tokens.Lexeme.T_EXT_ADDR_UINT16])
        if isinstance(name, str) and self.lexer.yylex['data'] is not None:
            self.symbols.set(
                name,
                U_Int16(addr),
                'variable',
                self.parse_immediate_value(self.lexer.yylex['data']))
        else:
            raise AssemblerParserError(
                f'Parser failed on variable "{name}"')

    def label(self, label: Yylex) -> None:
        name = label['data']
        addr = self.lexer.last_addr
        if isinstance(name, str):
            self.symbols.set(name, U_Int16(addr), 'label', U_Int16(addr))
        else:
            raise AssemblerParserError(
                f'Parser failed on label "{name}"')

    def operands(self) -> Deque[Yylex]:
        stack: Deque[Yylex] = deque()
        datatypes = [
            Tokens.Lexeme.T_IMM_UINT8,
            Tokens.Lexeme.T_IMM_UINT16,
            Tokens.Lexeme.T_DIR_ADDR_UINT8,
            Tokens.Lexeme.T_EXT_ADDR_UINT16,
            Tokens.Lexeme.T_DISP_ADDR_INT8,
        ]
        while True:
            try:
                self.take([
                    *list(Tokens.Register),
                    Tokens.Lexeme.T_COMMA,
                    *datatypes])
                stack.appendleft(self.lexer.yylex)
            except AssemblerParserError:
                self.lexer.retract()
                break
            except StopIteration:
                break
        return stack

    def instruction(
            self,
            instruction: Yylex) -> Tuple[Tokens.TokenEnum, Deque[Yylex]]:
        return (instruction['token'], self.operands())
