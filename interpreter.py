import lark
from lark.indenter import Indenter
from lark import Transformer
from pathlib import Path
import os
import re
import json

HEX = r"0x[0-9a-f]+"
REG = r"[a-zA-Z]+|t[0-9]+"  # Per semplicità al momento non considero i reali nomi di tutti i possibili registri
WILD = r"\?\?"

PUT = fr"PUT\(({REG}|{WILD})\) = ({REG}|{HEX}|{WILD})"
ST = fr"ST(le|be|{WILD}\(({REG}|{HEX}|{WILD})\)) = ({REG}|{HEX}|{WILD})"
ASSIGN = fr"(t[0-9]+|{WILD}) = "
GET = fr"GET:I(8|16|32|64|{WILD})\(({REG}|{HEX}|{WILD})\)"
LD = fr"LD(le|be|{WILD}):I(8|16|32|64|{WILD})\(({REG}|{HEX}|{WILD})\)"
OP = fr"(((Add|Sub|CmpEQ|CmpLT|Xor|And|DivS|Div|DivMod)(8|16|32|64|{WILD}))\(({REG}|{HEX}|{WILD}),({REG}|{HEX}|{WILD})\))|" \
     fr"((1Uto(8|16|32|64|{WILD}))|((8|16|32|64|{WILD})to1))\(({REG}|{HEX}|{WILD})\)"


# Classe usata da Lark per gestire l'indentazione
class TreeIndenter(Indenter):
    NL_type = '_NL'
    OPEN_PAREN_types = []
    CLOSE_PAREN_types = []
    INDENT_type = '_INDENT'
    DEDENT_type = '_DEDENT'
    tab_len = 8


# Classe usata da Lark per trasformare l'albero sintattico astratto in un formato più gestibile al fine di valutarlo
class MyTransformer(Transformer):
    def __init__(self):
        super().__init__()
        self.strings = {}

    def matches(self, items):
        variable = items[0]
        string = items[1]
        self.strings[variable] = string
        return json.loads('{{"{}": {}}}'.format(variable, string))

    def of_cond(self, items):
        return items

    def or_cond(self, items):
        return items

    def of(self, items):
        return items

    def them(self, items):
        return items

    def seq(self, items):
        return items

    def all(self, items):
        return items

    def any(self, items):
        return items

    def number(self, items):
        return items

    def and_cond(self, items):
        return items

    def stmt(self, items):
        return items

    def num(self, items):
        return items

    def parenthesis(self, items):
        return items

    def terminal(self, items):
        return items

    def condition(self, items):
        return items

    def sequence(self, items):
        return items

    def rule(self, items):
        return items

    def start(self, items):
        return items


class Interpreter:
    def __init__(self, rules_file, ir_file, binary):
        # Prendi il nome del file delle regole, del binario in VEX e della grammatica
        self.rules_file = os.path.abspath(rules_file)
        self.ir_file = ir_file
        self.grammar_path = Path(".").parent
        # Elementi utili per la valutazione della condizione
        self.tokens = ['and', 'or', '(', ')', 'any', 'all', 'them', 'of', '{', '}']
        self.high = ['and']
        self.low = ['or']
        file = open(binary, 'rb')
        self.raw = file.read()
        file.close()

    # Divido tra stringhe e condizione
    def __check_conditions(self, transformed_tree):
        matches = []
        conditions = []
        rule_name = transformed_tree[0]
        for el in transformed_tree[1]:
            if isinstance(el, dict):
                matches.append(el)  # Stringhe
            elif isinstance(el, list):
                conditions = el[0]  # Condizioni
        d = self.__flat_dictionary(matches)  # Appiattisco il risultato in un unico dizionario di stringhe da matchare
        # Normalizzo gli esadecimali delle stringhe
        for element in d.keys():
            hex_cond = re.findall(r"0x[0-9a-f]+", d[element], re.I)
            if hex_cond:
                d[element] = d[element].replace(hex_cond[0], hex(int(hex_cond[0], 0)))
                print(d[element])
        self.__search_conditions(conditions, d, rule_name)  # Cerco le condizioni nel VEX

    def __priority(self, op1, op2):
        if (op1 == '(' or op1 == ')') or (op2 == '(' or op2 == ')'):
            return -1
        if op1 in self.high and op2 in self.high:
            return 0
        if op1 in self.low and op2 in self.low:
            return 0
        if op1 in self.high and op2 in self.low:
            return 1
        if op1 in self.low and op2 in self.high:
            return -1

    def _wildcard(self, wild_string, instr):
        i = 0
        j = 0
        while i < len(wild_string) and i < len(instr):
            if wild_string[i] != instr[i]:
                if wild_string[i] == '?' and wild_string[i + 1] == '?':
                    wild_string = wild_string[i + 2:]
                    i = 0
                    if not wild_string:
                        return True
                    while wild_string[i] != instr[j]:
                        j += 1
                        if j >= len(instr):
                            return False
                    instr = instr[j:]
                    return self._wildcard(wild_string, instr)
                else:
                    return False
            i += 1
        if (i < len(instr) or i > len(instr)) or (i < len(wild_string) or i > len(wild_string)):
            return False
        else:
            return True

    def __check_vex(self, d, key):
        found = False
        imarks = []  # Lista degli indirizzi delle istruzioni da stampare
        with open(self.ir_file, 'r') as ir:
            for line in ir:
                hex_line = re.findall(r"0x[0-9a-f]+", line, re.I)
                if hex_line:
                    number = hex(int(hex_line[0], 0))
                    line = line.replace(hex_line[0], number)
                # Ricerco l'indirizzo da appendere alla lista
                mark = re.findall(r"^    00 | -+ IMark\(0x[0-9a-f]+, [0-9], [0-9]\) -+", line, re.I)
                if mark:
                    imarks.append(mark)
                if "??" in d[key]:
                    instr = re.split(r" \| ", line)
                    if len(instr) > 1:
                        instr = instr[1]
                        if self._wildcard(d[key], instr.strip()):
                            address = ''.join(re.findall(r"0x[0-9a-f]+", ''.join(imarks.pop()), re.I))
                            print('Condition ${} = "{}" is satisfied for the istruction'
                                  ' at address: {} with instruction "{}"'.format(key, d[key], address,
                                                                                 line.strip().split("| ")[1]))
                            found = True
                            return found
                # Se non siamo in presenza di wildcard verifico normalmente la presenza
                instr = re.split(r" \| ", line)
                if len(instr) > 1:
                    if d[key] == instr[1].strip():
                        address = ''.join(re.findall(r"0x[0-9a-f]+", ''.join(imarks.pop()), re.I))
                        print('Condition ${} = "{}" is satisfied for the istruction'
                              ' at address: {}'.format(key, d[key], address))
                        found = True
                        return found
            if not found:
                # print('Condition ${} = "{}" is not satisfied'.format(key, d[key]))
                found = False
                return found

    def __check_vex_row2(self, d, var):
        found = False
        imarks = []  # Lista degli indirizzi delle istruzioni da stampare
        dist = 0
        file = open(self.ir_file, 'r')
        lines = file.readlines()
        i = 0
        j = 0
        first_occurrence = 0
        last_imark = ''
        ind_imark = 0
        first_imark = ''
        previous_imarks = []
        while i < len(lines):
            line = lines[i]
            if j < len(var):
                key = var[j]
                if key.isnumeric():
                    dist = int(key)
                    j = j + 1
                    key = var[j]
                hex_line = re.findall(r"0x[0-9a-f]+", line, re.I)
                if hex_line:
                    number = hex(int(hex_line[0], 0))
                    line = line.replace(hex_line[0], number)
                # Ricerco l'indirizzo da appendere alla lista
                mark = re.findall(r"^    00 | -+ IMark\(0x[0-9a-f]+, [0-9], [0-9]\) -+", line, re.I)
                if mark:
                    address1 = 0
                    address2 = 0
                    if len(imarks) > 0:
                        address1 = ''.join(re.findall(r"0x[0-9a-f]+", ''.join(mark), re.I))
                        address2 = ''.join(re.findall(r"0x[0-9a-f]+", ''.join(imarks[-1]), re.I))
                    if mark not in imarks:
                        imarks.append(mark)
                    else:
                        i = i + 1
                        while True:
                            line = lines[i]
                            mark2 = re.findall(r"^    00 | -+ IMark\(0x[0-9a-f]+, [0-9], [0-9]\) -+", line, re.I)
                            if mark2 and mark2 not in imarks:
                                imarks.append(mark2)
                                break
                            i = i + 1
                    #if address1 < address2:
                    #    del imarks[:-1]
                if "??" in d[key]:
                    instr = re.split(r" \| ", line)
                    if len(instr) > 1:
                        instr = instr[1]
                        if self._wildcard(d[key], instr.strip()):
                            if last_imark != '':
                                ind_imark = imarks.index(last_imark)
                                if imarks.index(imarks[-1]) - ind_imark <= dist:
                                    address = ''.join(re.findall(r"0x[0-9a-f]+", ''.join(imarks[-1]), re.I))
                                    instruction = line.strip()
                                    if "|" in instruction:
                                        instruction = instruction.strip().split("| ")[1]
                                    print('Condition ${} = "{}" is satisfied for the istruction'
                                          ' at address: {} with instruction "{}"'.format(key, d[key], address,
                                                                                         instruction))
                                    found = True
                                    j = j + 1
                                    last_imark = imarks[-1]
                                    #ind_imark = imarks.index(last_imark)
                                else:
                                    found = False
                                    print("The next condition is satisfied in a wrong place")
                                    j = 0
                                    imarks.clear()
                                    imarks.append(first_imark)
                                    last_imark = ''
                                    dist = 0
                                    i = first_occurrence
                                    ind_imark = 0
                            else:
                                first_occurrence = i
                                first_imark = imarks[-1]
                                address = ''.join(re.findall(r"0x[0-9a-f]+", ''.join(imarks[-1]), re.I))
                                instruction = line.strip()
                                if "|" in instruction:
                                    instruction = instruction.strip().split("| ")[1]
                                print('Condition ${} = "{}" is satisfied for the istruction'
                                      ' at address: {} with instruction "{}"'.format(key, d[key], address,
                                                                                     instruction))
                                found = True
                                j = j + 1
                                last_imark = imarks[-1]
                                ind_imark = imarks.index(last_imark)
                instr = re.split(r" \| ", line)
                if len(instr) > 1:
                    if d[key] == instr[1].strip():
                        if last_imark != '':
                            ind_imark = imarks.index(last_imark)
                            if imarks.index(imarks[-1]) - ind_imark <= dist:
                                address = ''.join(re.findall(r"0x[0-9a-f]+", ''.join(imarks[-1]), re.I))
                                instruction = line.strip()
                                if "|" in instruction:
                                    instruction = instruction.strip().split("| ")[1]
                                print('Condition ${} = "{}" is satisfied for the istruction'
                                      ' at address: {} with instruction "{}"'.format(key, d[key], address,
                                                                                     instruction))
                                found = True
                                j = j + 1
                                last_imark = imarks[-1]
                            else:
                                found = False
                                print("The next condition is satisfied in a wrong place")
                                j = 0
                                imarks.clear()
                                imarks.append(last_imark)
                                last_imark = ''
                                dist = 0
                                i = first_occurrence
                                ind_imark = 0
                        else:
                            first_occurrence = i
                            address = ''.join(re.findall(r"0x[0-9a-f]+", ''.join(imarks[-1]), re.I))
                            instruction = line.strip()
                            if "|" in instruction:
                                instruction = instruction.strip().split("| ")[1]
                            print('Condition ${} = "{}" is satisfied for the istruction'
                                  ' at address: {} with instruction "{}"'.format(key, d[key], address,
                                                                                 instruction))
                            found = True
                            j = j + 1
                            last_imark = imarks[-1]
                            ind_imark = imarks.index(last_imark)
                i = i + 1
                if i == len(lines) and j < len(var):
                    if previous_imarks == imarks:
                        return False
                    previous_imarks = imarks
                    found = False
                    print("The next condition is not present")
                    j = 0
                    imarks.clear()
                    imarks.append(last_imark)
                    last_imark = ''
                    dist = 0
                    i = first_occurrence
                    ind_imark = 0
            else:
                return found
        return False

    def _is_raw(self, string):
        if re.match(f'({PUT}|{ST}|{WILD}|{ASSIGN}({GET}|{LD}|{WILD}|t([0-9]+|{WILD})|{HEX}|{OP}))', string):
            return False
        return True

    # Verifico che la singola stringa sia presente nel VEX
    def __find(self, d, element, token=''):
        if token == "all":
            if element == "them":
                for key in d.keys():
                    if not self._is_raw(d[key]):
                        if not self.__check_vex(d, key):
                            return False
                    else:
                        if not d[key].encode() in self.raw:
                            print(f"{d[key]} is not found")
                            return False
                        else:
                            print(f"{d[key]} found")
                return True

            else:  # something like all of ($x1 $x2 $y1) etc
                for el in element:
                    for key in d.keys():
                        if el in key:
                            if not self._is_raw(d[key]):
                                if not self.__check_vex(d, key):
                                    return False
                            else:
                                if not d[key].encode() in self.raw:
                                    print(f"{d[key]} is not found")
                                    return False
                                else:
                                    print(f"{d[key]} found")
                                    break
                return True
        elif token.isnumeric() or token == "any":  # at least "number" or at least one (any)
            num = int(token) if token.isnumeric() else 1
            count = 0
            if element == "them":
                for key in d.keys():
                    if count < num:
                        if not self._is_raw(d[key]):
                            if self.__check_vex(d, key):
                                count = count + 1
                        else:
                            if d[key].encode() in self.raw:
                                print(f"{d[key]} found")
                                count = count + 1
                    else:  # count >= num
                        return True
                if count >= num:
                    return True
                return False
            else:  # element is a list of variables to check
                for el in element:
                    for key in d.keys():
                        if el in key:
                            if count < num:
                                if not self._is_raw(d[key]):
                                    if self.__check_vex(d, key):
                                        count = count + 1
                                else:
                                    if d[key].encode() in self.raw:
                                        print(f"{d[key]} found")
                                        count = count + 1
                            else:
                                return True
                if count >= num:
                    return True
                else:
                    return False
        elif isinstance(element, list) and not token:  # Search in a row
            if self.__check_vex_row2(d, element):
                print("\n\n---------------- Found sequence: ", end='')
                for el in element:
                    if not el.isnumeric() and el not in self.tokens:
                        print("$" + el, end=' ')
                    else:
                        print(el, end=' ')
                print("----------------\n\n")
                return True
            else:
                return False
        else:
            if not self._is_raw(d[element]):
                return self.__check_vex(d, element)
            else:
                if d[element].encode() in self.raw:
                    print(f"{d[element]} found")
                    return True
                return False

    # Da lista di liste di elementi a un'unica lista di elementi in rappresentazione infissa
    def __infix(self, conditions):
        result = []
        if isinstance(conditions, (list, tuple)):
            for x in conditions:
                result.extend(self.__infix(x))
        else:
            result.append(conditions)
        return result

    def __evaluate(self, infix, d):
        operator_stack = []
        stack = []
        i = 0
        while i < len(infix):
            if infix[i] == ' ':
                continue
            elif infix[i] == '(':
                operator_stack.append(infix[i])
            elif infix[i] == ')':
                val2 = stack.pop()
                val1 = stack.pop()
                op = operator_stack.pop()
                if op == 'and':
                    stack.append(val1 and val2)
                elif op == 'or':
                    stack.append(val1 or val2)
                operator_stack.pop()
            elif infix[i] == 'any' or infix[i] == 'all' or infix[i].isnumeric():
                token = infix[i]
                i = i + 2
                var = []
                if infix[i] == '(':
                    i = i + 1
                    while infix[i] != ')':
                        var.append(infix[i])
                        i = i + 1
                    # operator_stack.pop()
                if infix[i] == 'them':  # infix[i] == 'them'
                    stack.append(self.__find(d, infix[i], token=token))
                else:  # something like all of ($x, $y) or 2 of ($x, $y, $z) or any of ($x, $y)
                    stack.append(self.__find(d, var, token))
            elif infix[i] == '{':
                var = []
                i = i + 1
                while infix[i] != '}':
                    var.append(infix[i])
                    i = i + 1
                stack.append(self.__find(d, var))
            elif infix[i] in self.tokens:
                while len(operator_stack) != 0 and self.__priority(operator_stack[-1], infix[i]) >= 0:
                    val2 = stack.pop()
                    val1 = stack.pop()
                    op = operator_stack.pop()
                    if op == 'and':
                        stack.append(val1 and val2)
                    elif op == 'or':
                        stack.append(val1 or val2)
                operator_stack.append(infix[i])
            else:
                stack.append(self.__find(d, infix[i]))
            i = i + 1
        while len(operator_stack) != 0:
            val2 = stack.pop()
            val1 = stack.pop()
            op = operator_stack.pop()
            if op == 'and':
                stack.append(val1 and val2)
            elif op == 'or':
                stack.append(val1 or val2)
        return stack[-1]

    def __flatten(self, possiblyNestedList):
        # Flatten arbitrarily nested list
        if not isinstance(possiblyNestedList, list):
            return
        flattened = []
        for item in possiblyNestedList:
            if isinstance(item, list):
                flattened.extend(self.__flatten(item))
            else:
                flattened.append(item)
        return flattened

    # Verifico che la condizione sia presente tra le stringhe e se lo è verifico che la stringa esista nel codice VEX
    def __search_conditions(self, conditions, d, rule_name):
        condition = conditions[0]
        # print(conditions)
        # print(condition)
        ret = False
        infix = self.__infix(conditions)
        #print(infix)
        cond = ''.join(
            "$" + val + " " if val not in self.tokens and not val.isnumeric() else val + " " for val in infix).strip()
        # Se la condizione non è composta
        if len(conditions) == 1:
            if infix[0] == "all" or infix[0] == 'any' or infix[0].isnumeric():
                i = 0
                while i < len(infix):
                    token = infix[i]
                    i = i + 2
                    var = []
                    if infix[i] == '(':
                        i = i + 1
                        while infix[i] != ')':
                            var.append(infix[i])
                            i = i + 1
                    if infix[i] == 'them':  # infix[i] == 'them'
                        ret = self.__find(d, infix[i], token=token)
                    else:  # something like all of ($x, $y) or 2 of ($x, $y, $z) or any of ($x, $y)
                        ret = self.__find(d, var, token)
                    i = i + 1
            else:
                ret = self.__find(d, condition)
            if ret:
                print('The condition "{}" from rule: "{}" is satisfied'.format(cond, rule_name))
            else:
                print('The condition "{}" from rule: "{}" is not satisfied'.format(cond, rule_name))

        # Se la condizione è composta
        else:
            # Verifico che la condizione sia soddisfatta
            if self.__evaluate(infix, d):
                print('The condition "{}" from rule: "{}" is satisfied'.format(cond.strip(), rule_name))
            else:
                print('The condition "{}" from rule: "{}" is not satisfied'.format(cond.strip(), rule_name))

    def __flat_dictionary(self, matches):
        d = {}
        for dictionary in matches:
            d.update(dictionary)
        return d

    def interprets(self):
        # Crea il parser utilizzando la grammatica
        parser = lark.Lark.open(self.grammar_path / 'grammar.lark', rel_to=__file__, parser='lalr',
                                postlex=TreeIndenter(), transformer=MyTransformer())

        # Leggi il contenuto delle regole
        with open(self.rules_file, 'r') as f:
            data = f.read()
            '''
            Parserizza il file delle regole e crea l'AST che viene trasformato in una formato più gestibile dalla classe
            MyTransformer
            '''
            transformed_tree = parser.parse(data)
            # print(transformed_tree)
        # Distinzione tra file di regole con una o più regole
        if isinstance(transformed_tree[0], str):
            self.__check_conditions(transformed_tree)  # Una regola
        else:
            for tree in transformed_tree:
                self.__check_conditions(tree)  # Più regole


def main():
    x = Interpreter("rules/rule1.txt", "/tmp/ir-5ed1c054-545e-11ed-a5db-beab88cf32ef")
    x.interprets()


if __name__ == '__main__':
    main()
