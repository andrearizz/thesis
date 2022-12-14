import angr
import os
import sys
import uuid

import archinfo


def next_key(d, key):
    keys = iter(d)
    key in keys  # Terribile ma efficace
    return next(keys, sys.maxsize)


class Lifter:
    def __init__(self, binary, function='', start_addr=0, end_addr=0):
        self.binary = os.path.abspath(binary)

        # Carica il binario
        self.proj = angr.Project(binary, load_options={'auto_load_libs': False})

        # Prendi il control flow graph
        self.cfg = self.proj.analyses.CFGFast()

        self.function = function
        self.start_addr = start_addr
        self.end_addr = end_addr

        self.functions_addr = self.cfg.kb.functions

    # Ottieni tutti i super block del binario
    def __all_sb(self):
        super_blocks = []
        for addr in self.functions_addr:
            super_blocks.append(list(self.functions_addr[addr].block_addrs_set))

        # Flat basic blocks
        super_blocks = [item for sublist in super_blocks for item in sublist]
        super_blocks.sort()
        # La lista di ritorno è composta dagli indirizzi d'inizio di ogni super block
        return super_blocks

    # Super block da liftare appatartenenti ad una funzione indicata
    def __function_bb(self):
        basic_blocks = []
        for addr in self.functions_addr:
            if self.functions_addr[addr].name == self.function:
                basic_blocks.append(list(self.functions_addr[addr].block_addrs_set))
        # Flat Super blocks
        basic_blocks = [item for sublist in basic_blocks for item in sublist]
        basic_blocks.sort()
        # La lista di ritorno è composta dagli indirizzi di inizio di ogni basic block
        return basic_blocks

    # Super block da liftare in un range dato
    def __range_bb(self):
        basic_blocks = []
        start = int(self.start_addr)
        end = int(self.end_addr)
        for addr in self.functions_addr:
            next_addr = next_key(self.functions_addr._function_map, addr)
            if int(addr <= start < next_addr or start <= addr <= end):
                print(self.functions_addr[addr].name)
                basic_blocks.append(list(self.functions_addr[addr].block_addrs_set))
        # Flat Super blocks
        basic_blocks = [item for sublist in basic_blocks for item in sublist]
        basic_blocks.sort()
        i = 0
        while i < len(basic_blocks):
            if (basic_blocks[i] < start or basic_blocks[i] > end) and not (basic_blocks[i] <= start and end < basic_blocks[i + 1]):
                del basic_blocks[i]
            else:
                i = i + 1
        # La lista di ritorno è composta dagli indirizzi di inizio di ogni basic block
        return basic_blocks

    # Super block da liftare in IR a partire da un indirizzo
    def __addr_bb(self):
        basic_blocks = []
        start = int(self.start_addr)
        print(hex(start))
        for addr in self.functions_addr:
            next_addr = next_key(self.functions_addr._function_map, addr)
            if int(addr <= start < next_addr or addr >= start):
                basic_blocks.append(list(self.functions_addr[addr].block_addrs_set))
        # Flat Super blocks
        basic_blocks = [item for sublist in basic_blocks for item in sublist]
        basic_blocks.sort()
        # La lista di ritorno è composta dagli indirizzi di inizio di ogni basic block
        return basic_blocks

    # Ottieni la lista di ogni super block in VEX
    def __irsb(self, super_blocks):
        irsbs = []
        for block in super_blocks:
            irsbs.append(self.proj.factory.block(block).vex)
        return irsbs

    def lift(self):
        # Crea un file temporaneo in cui scrivere il codice in VEX
        uid = uuid.uuid1()
        filename = "/tmp/ir-{}-{}".format(uid, self.proj.arch.name)

        if self.function:
            irsbs = self.__irsb(self.__function_bb())
        elif self.start_addr and self.end_addr:
            irsbs = self.__irsb(self.__range_bb())
        elif self.start_addr and not self.end_addr:
            irsbs = self.__irsb(self.__addr_bb())
        else:
            # Ottieni tutti i basic block
            irsbs = self.__irsb(self.__all_sb())

        for ir in irsbs:
            with open(filename, "a") as sys.stdout:  # Redirigi lo standard output verso il file temporaneo
                ir.pp()
        # Resetta lo standard output
        sys.stdout = sys.__stdout__
        return filename


def main():
    lifter = Lifter("binaries/reverse_shell", start_addr=0x40125b, end_addr=0x401265)
    print(lifter.lift())


if __name__ == '__main__':
    main()
