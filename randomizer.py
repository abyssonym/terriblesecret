from randomtools.tablereader import TableObject
from randomtools.utils import (
    classproperty, mutate_normal, shuffle_bits,
    utilrandom as random)
from randomtools.interface import (
    get_outfile, get_seed, get_flags, run_interface, rewrite_snes_meta,
    clean_and_write, finish_interface)
from os import path


RANDOMIZE = True
VERSION = 2
ALL_OBJECTS = None

try:
    from sys import _MEIPASS
    tblpath = path.join(_MEIPASS, "tables")
except ImportError:
    tblpath = "tables"
TEXTTABLEFILE = path.join(tblpath, "mq.tbl")
ITEMNAMESFILE = path.join(tblpath, "itemnames.txt")
itemnames = [line.strip() for line in open(ITEMNAMESFILE).readlines()]
CONSUMABLES = [0x10, 0x11, 0x12, 0x13, 0xDD, 0xDE, 0xDF]
BROKEN_ITEMS = range(0x10) + [0x2c, 0x2d, 0x2e, 0x36, 0x37, 0x38, 0x39, 0x3c]
BANNED_ITEMS = [0x07, 0x2a]  # Thunder Rock, Jumbo Bomb
chest_items = None


def populate_chest_items():
    global chest_items
    chest_items = [i for i in range(len(itemnames))
                   if i not in CONSUMABLES + BANNED_ITEMS]
    random.shuffle(chest_items)


texttable = {}
for line in open(TEXTTABLEFILE):
    a, b = line.strip("\n").split("=")
    a = int(a, 0x10)
    texttable[a] = b
    texttable[b] = a


def write_title_screen(outfile, seed, flags):
    assert texttable["A"] == 0x9a
    pointer = 0x60EDB
    seed = "{0:0>10}".format(seed)
    flags = "{0: <4}".format(flags)
    version = "v{0: <3}".format(VERSION)
    assert len(seed) == 10
    assert len(flags) == 4
    space = [chr(0xFE)]
    to_write = "".join(
        (space*2) +
        [chr(texttable[c]) for c in seed[-5:]] +
        (space) +
        [chr(texttable[c]) for c in flags.upper()] +
        [chr(texttable[c]) for c in version.upper()] +
        [chr(texttable[c]) for c in "TERRIBLE"] +
        (space*len("Press any button")) +
        [chr(texttable[c]) for c in seed[:5]] +
        (space*2) +
        [chr(texttable[c]) for c in "SECRET"] +
        (space*2)
        )
    to_write = to_write.replace(chr(texttable[" "]), chr(0xFE))
    f = open(outfile, "r+b")
    f.seek(pointer)
    f.write(to_write)
    f.close()


def bytes_to_text(data):
    return "".join([texttable[d] if d in texttable else "~" for d in data])


class TreasureIndexObject(TableObject):
    flag = "t"
    consumable_options = (
        [0x10] * 69 +
        [0x11] * 57 +
        [0x12] * 3 +
        [0x13] * 19 +
        [0xdd] * 19 +
        [0xde] * 55 +
        [0xdf] * 1
        )

    @classproperty
    def after_order(self):
        return [BattleRewardObject]

    @property
    def is_consumable(self):
        return self.contents in CONSUMABLES

    @property
    def is_key(self):
        return self.contents < 0x10

    @property
    def contents_name(self):
        additional = {0xDD: "Explosive",
                      0xDE: "Arrow",
                      0xDF: "Ninja Star",
                      }
        if self.contents in additional:
            return additional[self.contents]
        return itemnames[self.contents]

    @classmethod
    def mutate_all(self):
        chests = list(self.every)
        random.shuffle(chests)
        for o in chests:
            if hasattr(o, "mutated") and o.mutated:
                continue
            o.mutate()
            o.mutate_bits()
            o.mutated = True

    def mutate(self):
        global chest_items
        if self.is_key or self.contents == 0xDD:
            return

        v = random.randint(1, 7)
        if self.is_consumable and v != 7:
            self.contents = random.choice(self.consumable_options)
            return

        while True:
            if not chest_items:
                populate_chest_items()
            value = chest_items.pop()
            if value in BROKEN_ITEMS and random.randint(1, 10) != 10:
                chest_items = [value] + chest_items
                continue
            break
        self.contents = value


class CombatObject(object):
    mutate_attributes = {"power": None}

    def mutate(self):
        super(CombatObject, self).mutate()
        self.status = shuffle_bits(self.status)


class ItemNameMixin(object):
    first_name_index = 0

    @property
    def name(self):
        return itemnames[self.index + self.first_name_index]


class WeaponObject(CombatObject, ItemNameMixin, TableObject):
    first_name_index = 32
    flag = "c"
    intershuffle_attributes = ["statboost", "status"]

    @property
    def rank(self):
        return self.power

    def mutate(self):
        super(WeaponObject, self).mutate()
        if random.randint(1, 3) == 3:
            element = (1 << random.randint(3, 7))
            self.element |= element


class AttackObject(CombatObject, TableObject):
    flag = "m"


class ArmorObject(CombatObject, ItemNameMixin, TableObject):
    first_name_index = 47
    flag = "c"
    intershuffle_attributes = ["statboost", "element", "status"]

    @property
    def rank(self):
        return self.power

    def mutate(self):
        super(ArmorObject, self).mutate()
        if random.randint(1, 4) == 4:
            self.element = shuffle_bits(self.element)
        else:
            value = shuffle_bits(self.element >> 3, size=5)
            value = value << 3
            self.element = self.element & 0x7
            self.element |= value


class DropObject(TableObject):
    flag = "t"
    flag_description = "treasure"
    mutate_attributes = {"xp": None,
                         "gp": None,
                         }


class MonsterObject(TableObject):
    flag = "m"
    flag_description = "monster stats"
    mutate_attributes = {"hp": (0, 0xFFFE),
                         "strength": None,
                         "defense": None,
                         "speed": None,
                         "magic": None,
                         }
    intershuffle_attributes = [
        "resistances", "weaknesses",
        ]

    @property
    def intershuffle_valid(self):
        return False

    @property
    def is_boss(self):
        return self.index >= 57

    @property
    def name(self):
        return MonsterNameObject.get(self.index).name

    @property
    def drop(self):
        return DropObject.get(self.index)

    @property
    def xp(self):
        return self.drop.xp * 3

    @property
    def gp(self):
        return self.drop.gp * 3

    def mutate(self):
        oldstats = {}
        for key in self.mutate_attributes:
            oldstats[key] = getattr(self, key)
        super(MonsterObject, self).mutate()
        if self.is_boss:
            for (attr, oldval) in oldstats.items():
                if getattr(self, attr) < oldval:
                    setattr(self, attr, oldval)
        for attr in ["resistances", "weaknesses", "immunities"]:
            if self.is_boss and attr == "immunities":
                continue
            value = getattr(self, attr) >> 4
            value = shuffle_bits(value, size=4) << 4
        while random.choice([True, False]):
            attr = random.choice(["resistances", "weaknesses", "immunities"])
            value = getattr(self, attr)
            if attr != "immunities" and bin(value).count("1") > 6:
                continue
            flag = (1 << random.randint(0, 7))
            if ((attr == "weaknesses" or not self.is_boss) and
                    random.randint(1, 10) == 10):
                value ^= flag
            else:
                if attr != "immunities" and bin(value).count("1") > 4:
                    continue
                value |= flag
            setattr(self, attr, value)
        self.resistances = self.resistances & 0xF0
        if random.randint(1, 4) == 4:
            self.counter &= 0x0F
            newcounter = random.choice([0, 0, 0x10, 0x20, 0x40, 0x80, 0x80])
            self.counter |= newcounter


class BattleRewardObject(TableObject):
    flag = "t"

    @property
    def is_xp(self):
        return bool(self.reward & 0x8000)

    @property
    def is_item(self):
        return bool(self.reward & 0x4000)

    @property
    def is_gp(self):
        return not (self.is_xp or self.is_item)

    @property
    def value(self):
        return self.reward & 0x3FF

    @property
    def contents_name(self):
        if not self.is_item:
            return "NONE"
        return itemnames[self.reward & 0xFF]

    def cleanup(self):
        assert not (self.is_xp and self.is_item)
        assert not self.reward & 0x3C00

    def mutate(self):
        if self.is_item and self.value == 0x14:
            # Exit battlefield is fixed
            return
        self.reward = 0
        rewardtype = random.choice(["xp", "item", "item", "gp"])
        if rewardtype == "item":
            self.reward |= 0x4000
            if not chest_items:
                populate_chest_items()
            self.reward |= chest_items.pop()
        else:
            if rewardtype == "xp":
                self.reward |= 0x8000
            self.reward |= random.randint(1, 0x3FF)


class MonsterNameObject(TableObject):
    @property
    def name(self):
        return bytes_to_text(self.text)


class CharacterObject(TableObject):
    flag = "c"
    flag_description = "characters"
    mutate_attributes = {"level": (1, 99),
                         "max_hp": (40, 32000),
                         "attack": (1, 99),
                         "defense": (1, 99),
                         "speed": (1, 99),
                         "magic": (1, 99),
                         "accuracy": (1, 99),
                         "white": (0, 99),
                         "black": (0, 99),
                         "wizard": (0, 99),
                         }
    intershuffle_attributes = [
        "max_hp", "attack", "defense", "speed", "magic", "accuracy",
        ("white", "black", "known_magic"), ("wizard", "known_wizard")]

    @property
    def rank(self):
        return self.level

    @property
    def name(self):
        return bytes_to_text(self.name_text)

    @property
    def known_black(self):
        return self.known_magic & 0xF

    @property
    def known_white(self):
        return self.known_magic >> 4

    def mutate(self):
        self.known_magic = shuffle_bits(self.known_magic)
        known_wizard = self.known_wizard >> 4
        self.known_wizard = shuffle_bits(known_wizard, size=4) << 4
        super(CharacterObject, self).mutate()

    def cleanup(self):
        self.max_hp = int(round(self.max_hp / 40.0)) * 40
        assert self.max_hp >= 40
        assert not self.max_hp % 40
        self.current_hp = self.max_hp
        if ((self.known_white and self.black and
                not self.white and not self.known_black) or
                (self.known_black and self.white and
                    not self.black and not self.known_white)):
            self.white, self.black = self.black, self.white
        if "DemoPlay" in self.name:
            return
        for attr in ["white", "black", "wizard"]:
            if getattr(self, "known_%s" % attr):
                avg = (self.white + self.black + self.wizard) / 3
                avg = max(avg, 1)
                setattr(self, attr, max(getattr(self, attr), avg))
            else:
                setattr(self, attr, 0)
        for attr in ["attack", "defense", "speed", "magic",
                     "white", "black", "wizard"]:
            setattr(self, "%s2" % attr, getattr(self, attr))


class BattleRoundsObject(TableObject):
    flag = "t"
    mutate_attributes = {"num_rounds": (0, 0xFF)}


if __name__ == "__main__":
    print ('You are using the Final Fantasy Mystic Quest "A Terrible Secret" '
           'randomizer version %s.' % VERSION)
    ALL_OBJECTS = [g for g in globals().values()
                   if isinstance(g, type) and issubclass(g, TableObject)
                   and g not in [TableObject]]
    run_interface(ALL_OBJECTS, snes=True)
    hexify = lambda x: "{0:0>2}".format("%x" % x)
    numify = lambda x: "{0: >3}".format(x)
    minmax = lambda x: (min(x), max(x))
    clean_and_write(ALL_OBJECTS)
    write_title_screen(get_outfile(), get_seed(), get_flags())
    rewrite_snes_meta("FFMQ-R", VERSION, megabits=24, lorom=True)
    finish_interface()
