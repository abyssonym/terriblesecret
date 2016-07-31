from randomtools.tablereader import TableObject
from randomtools.utils import (
    classproperty, mutate_normal, shuffle_bits,
    utilrandom as random)
from randomtools.interface import (
    get_outfile, get_seed, get_flags, run_interface, rewrite_snes_meta,
    clean_and_write, finish_interface)
from os import path


RANDOMIZE = True
VERSION = 5
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
BANNED_ITEMS = [0x07, 0x08, 0x29, 0x2a, 0x2b]  # Rock, Cap, All bombs
BROKEN_ITEMS = [i for i in range(0x10) +
    [0x2c, 0x2d, 0x2e, 0x36, 0x37, 0x38, 0x39, 0x3c] if i not in BANNED_ITEMS]
UNDESIRABLE_ITEMS = [0x20, 0x23, 0x26, 0x2c, 0x2d, 0x2e,
                     0x32, 0x35, 0x36, 0x37, 0x38, 0x3c]
UNDESIRABLE_ITEMS = sorted(set(UNDESIRABLE_ITEMS + BROKEN_ITEMS))
DESIRABLE_ITEMS = [i for i in range(0x10, 0x40) if i == 0x12 or i not in
   CONSUMABLES + UNDESIRABLE_ITEMS + BROKEN_ITEMS + BANNED_ITEMS]
assert not set(BANNED_ITEMS) & set(
    DESIRABLE_ITEMS + UNDESIRABLE_ITEMS + BROKEN_ITEMS + CONSUMABLES)
assert not set(DESIRABLE_ITEMS) & set(UNDESIRABLE_ITEMS)
chest_items = None


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
    desirable_left = list(DESIRABLE_ITEMS)
    undesirable_left = list(UNDESIRABLE_ITEMS)
    well_hidden = set([])

    def __repr__(self):
        return "%x: %s" % (self.index, self.contents_name)

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
        random.shuffle(self.desirable_left)
        random.shuffle(self.undesirable_left)
        for o in chests:
            if hasattr(o, "mutated") and o.mutated:
                continue
            o.mutate()
            o.mutated = True

    def mutate(self):
        global chest_items
        if self.is_key:
            return

        if self.index == 5:
            # focus tower bomb chest
            return

        any_left = self.desirable_left + self.undesirable_left
        value = None
        if self.is_consumable and (not any_left or random.randint(1, 7) != 7):
            self.contents = random.choice(self.consumable_options)
            return
        elif self.is_consumable:
            if self.undesirable_left and (
                    not self.desirable_left or random.randint(1, 10) != 10):
                value = self.undesirable_left.pop()
            else:
                value = self.desirable_left.pop()

        if value is None:
            if self.desirable_left:
                value = self.desirable_left.pop()
            elif self.undesirable_left:
                value = self.undesirable_left.pop()
            else:
                value = 0x12  # seed

        if (value not in [0x12, 0x14] and value in DESIRABLE_ITEMS
                and self.is_consumable):
            self.well_hidden.add(value)
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
        "resistances", "weaknesses", "immunities",
        "hp", "strength", "defense", "speed", "magic",
        ]

    @classproperty
    def after_order(self):
        return [FormationObject]

    @property
    def rank(self):
        values = [getattr(self, attr) for attr in
                  ["hp", "defense", "speed"]]
        values = [v for v in values if v]
        values += [max(self.strength, self.magic)]
        rank = 1
        for v in values:
            rank *= v
        return rank

    @property
    def intershuffle_valid(self):
        if self.hp < 200:
            return False
        return not self.is_boss

    @property
    def is_boss(self):
        return self.index >= 0x40

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
        if self.index == 0x42:
            # Behemoth
            return
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
        if self.hp < 200 or self.index in [0x43, 0x4a]:
            return
        if random.randint(1, 4) == 4:
            self.counter &= 0x0F
            newcounter = random.choice([0, 0, 0x10, 0x20, 0x40, 0x80, 0x80])
            self.counter |= newcounter


class BattleRewardObject(TableObject):
    flag = "t"

    @classproperty
    def after_order(self):
        return [BattleFormationObject, TreasureIndexObject]

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

    @property
    def contents_description(self):
        if self.is_item:
            return self.contents_name
        elif self.is_xp:
            return "%s XP" % self.value
        elif self.is_gp:
            return "%s GP" % self.value

    def cleanup(self):
        assert not (self.is_xp and self.is_item)
        assert not self.reward & 0x3C00

    @classmethod
    def mutate_all(self):
        brs = list(self.every)
        random.shuffle(brs)
        for o in brs:
            if hasattr(o, "mutated") and o.mutated:
                continue
            o.mutate()
            o.mutated = True

    def mutate(self):
        if self.is_item and self.value == 0x14:
            # Exit battlefield is fixed
            return

        self.reward = 0
        done_items = [t.reward & 0xFF for t in BattleRewardObject.every
                      if hasattr(t, "mutated") and t.mutated
                      and t.reward & 0x4000]
        assert len(done_items) == len(set(done_items))
        if TreasureIndexObject.desirable_left:
            value = TreasureIndexObject.desirable_left.pop()
            if value == 0x14 and TreasureIndexObject.desirable_left:
                value = TreasureIndexObject.desirable_left.pop()
            if value != 0x14:
                self.reward |= 0x4000
                self.reward |= value
        if TreasureIndexObject.undesirable_left:
            remaining = [i for i in TreasureIndexObject.undesirable_left
                         if i not in BROKEN_ITEMS]
            if remaining:
                value = remaining.pop()
                self.reward |= 0x4000
                self.reward |= value
                TreasureIndexObject.undesirable_left.remove(value)

        if self.reward == 0:
            rewardtype = random.choice(["xp", "xp", "item", "gp"])
            if rewardtype == "item":
                self.reward |= 0x4000
                self.reward |= random.choice(
                    sorted(set(DESIRABLE_ITEMS + UNDESIRABLE_ITEMS)))
            else:
                if rewardtype == "xp":
                    self.reward |= 0x8000
                self.reward |= random.randint(1, 0x3FF)

        if self.reward & 0x4000 and (self.reward & 0xFF) in done_items:
            self.reward = 0
            return self.mutate()


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

    @classproperty
    def after_order(self):
        return [BattleFormationObject]


class FormationObject(TableObject):
    flag = "f"
    flag_description = "formations"
    done_bosses = set([])
    banned_bosses = [0x4c, 0x4d, 0x4e, 0x4f, 0x50]
    unused = []

    @classproperty
    def after_order(self):
        return [BattleFormationObject]

    @property
    def maxrank(self):
        return max([e.rank for e in self.enemies])

    def read_data(self, *args, **kwargs):
        super(FormationObject, self).read_data(*args, **kwargs)
        if self.pointer >= BattleFormationObject.get(0).pointer:
            self.enemy_ids = [0xFF] * 3
            self.unknown = 0

    def __repr__(self):
        if self.is_broken:
            return "%x: BROKEN" % self.index
        return "%x: %s (%x)" % (self.index,
            ", ".join([e.name.strip() for e in self.enemies]), self.unknown)

    @property
    def is_broken(self):
        return any([(m & 0x7F) > 0x50 and m != 0xFF for m in self.enemy_ids])

    @property
    def is_boss(self):
        return self.enemies and self.leader.is_boss

    @property
    def enemies(self):
        return [MonsterObject.get(eid & 0x7F) for eid in self.enemy_ids
                if eid < 0xFF]

    @property
    def leader(self):
        if not self.enemies:
            return None
        if len(self.enemies) >= 2:
            return MonsterObject.get(self.enemy_ids[1] & 0x7F)
        else:
            return self.enemies[0]

    @property
    def rank(self):
        if self.is_broken or not self.enemies:
            return -1
        ranks = sorted([e.rank for e in self.enemies], reverse=True)
        total = 0
        for m, r in zip([1, 0.5, 0.25], ranks):
            total += m * r
        return int(total)

    @classmethod
    def find_unused(self):
        used = set([])
        for bf in BattleFormationObject.every:
            used |= set(bf.formation_ids)
        self.unused = [f for f in FormationObject.every
                       if f.index not in used]
        for f in self.unused:
            f.enemy_ids = [0xFF] * 3
            f.unknown = 0

    @classmethod
    def get_unused(self):
        if not self.unused:
            self.find_unused()
        return self.unused.pop()

    def mutate(self):
        if not self.unused:
            self.find_unused()
        old_ids = list(self.enemy_ids)
        if self.is_boss:
            boss = self.leader
            boss_index = boss.index
            if boss_index == 0x50:
                return
            new = []
            upper = self.leader.rank
            for e in self.enemy_ids:
                if e == boss_index:
                    continue
                if e == 0xFF and random.choice([True, False]):
                    continue
                if e == 0xFF:
                    lower = 0
                else:
                    lower = MonsterObject.get(e).rank
                candidates = [m for m in MonsterObject.ranked
                              if lower <= m.rank < upper
                              and m.index not in self.banned_bosses]
                if not candidates:
                    return
                upper_index = max(len(candidates)-2, 0)
                index = random.randint(0, upper_index)
                index = random.randint(0, index)
                chosen = candidates[index]
                upper = min(upper, chosen.rank)
                new.append(chosen.index)
            if len(new) == 2:
                new = [new[0], boss_index, new[1]]
            else:
                new = [boss_index] + new
            while len(new) < 3:
                new += [0xFF]
            self.enemy_ids = new
            return

        if len(self.enemies) <= 1:
            return

        ranked_monsters = MonsterObject.ranked
        for i, e in enumerate(self.enemies):
            if i == len(self.enemies)-2:
                continue
            index = ranked_monsters.index(e)
            width = random.randint(2, random.randint(2, random.randint(
                2, len(ranked_monsters))))
            candidates = ranked_monsters[max(index-width, 0):index+width+1]
            assert e in candidates
            new = e.get_similar(candidates)
            if new.index in self.banned_bosses:
                continue
            if new in self.done_bosses and random.randint(1, 10) != 10:
                continue
            self.enemy_ids[i] = new.index
            if new.is_boss:
                self.done_bosses.add(new)

        new_tuple = sorted(tuple(self.enemy_ids))
        if new_tuple == sorted(tuple(old_ids)):
            return
        for f in FormationObject.every:
            if f.index == self.index:
                continue
            if sorted(tuple(f.enemy_ids)) == new_tuple:
                self.enemy_ids = old_ids
                break


class BattleFormationObject(TableObject):
    flag = "t"

    @classproperty
    def after_order(self):
        return [TreasureIndexObject]

    def __repr__(self):
        if self.index < 20:
            rounds, reward = (BattleRoundsObject.get(self.index).num_rounds,
                              BattleRewardObject.get(self.index).contents_description)
        else:
            rounds, reward = "N/A", "N/A"
        return "%x %s %s\n%s" % (
            self.index, rounds, reward,
            "\n".join([str(f) for f in self.formations]))

    @property
    def formations(self):
        return [FormationObject.get(f) for f in self.formation_ids]

    @property
    def rank(self):
        return max(f.rank for f in self.formations)

    @property
    def is_boss(self):
        return len(set(self.formation_ids)) == 1 and self.formations[0].is_boss

    def mutate(self):
        if self.index == 0:
            self.become_boss()
            f = self.formations[0]
            f.enemy_ids = [0x42, 0x42, 0xFF]
            return

        if self.index < 20 and random.randint(1, 4) == 4:
            self.become_boss()

        if self.is_boss:
            return

        if self.index >= 20:
            leaders = [f.leader for f in self.formations]
            maxrank = max([f.maxrank for f in self.formations])
            assert len(set(leaders)) == 1
            leader = leaders[0]
            candidates = [f for f in FormationObject.every
                          if f.leader == leader and f.maxrank <= maxrank]
        else:
            candidates = list(FormationObject.every)

        new_ids = [f.get_similar(candidates).index for f in self.formations]
        if len(set(new_ids)) < len(set(self.formation_ids)):
            return
        self.formation_ids = new_ids

    def become_boss(self):
        flamerus_rank = MonsterObject.get(0x4a).rank
        battlefields = [bf for bf in BattleFormationObject.ranked
                        if bf.index < 20]
        my_index = battlefields.index(self)
        candidates = [m for m in MonsterObject.ranked
                      if m.rank >= flamerus_rank]
        new_index = int(round(my_index * (len(candidates) / 20.0)))
        new_index = mutate_normal(new_index, minimum=0,
                                  maximum=len(candidates)-1)
        leader = candidates[new_index]
        candidates = [m for m in MonsterObject.ranked
                      if m.rank < leader.rank]
        max_index = len(candidates)-1
        follow_index = random.randint(random.randint(0, max_index), max_index)
        follower = candidates[follow_index].index
        if random.randint(0, max_index) >= follow_index:
            follow2_index = random.randint(
                random.randint(0, follow_index), follow_index)
            follower2 = candidates[follow2_index].index
        else:
            follower2 = 0xFF
        new_ids = [follower, leader.index, follower2]
        f = FormationObject.get_unused()
        f.enemy_ids = new_ids
        self.formation_ids = [f.index] * 3
        f.mutated = True
        br = BattleRoundsObject.get(self.index)
        br.num_rounds = 1
        br.mutated = True
        br2 = BattleRewardObject.get(self.index)
        br2.reward = 0x4000
        done_items = [t.reward & 0xFF for t in BattleRewardObject.every
                      if hasattr(t, "mutated") and t.mutated
                      and t.reward & 0x4000]
        if TreasureIndexObject.well_hidden:
            value = random.choice(sorted(TreasureIndexObject.well_hidden))
            TreasureIndexObject.well_hidden.remove(value)
        else:
            value = random.choice([i for i in DESIRABLE_ITEMS
                                   if i != 0x14 and i not in done_items])
        br2.reward |= value
        br2.mutated = True

    @classmethod
    def mutate_all(cls):
        battlefields = [cls.get(i) for i in range(20)]
        everything_else = [c for c in cls.every if c not in battlefields]
        random.shuffle(battlefields)
        random.shuffle(everything_else)
        for o in everything_else + battlefields:
            if hasattr(o, "mutated") and o.mutated:
                continue
            o.mutate()
            o.mutated = True


if __name__ == "__main__":
    try:
        print ('You are using the Final Fantasy Mystic Quest "A Terrible Secret" '
               'randomizer version %s.' % VERSION)
        ALL_OBJECTS = [g for g in globals().values()
                       if isinstance(g, type) and issubclass(g, TableObject)
                       and g not in [TableObject]]
        run_interface(ALL_OBJECTS, snes=True)
        DemoPlay = CharacterObject.get(0)
        DemoPlay.name_text = [texttable[c] for c in "Abyssnym"]
        while len(DemoPlay.name_text) < 16:
            DemoPlay.name_text += [0x03]
        hexify = lambda x: "{0:0>2}".format("%x" % x)
        numify = lambda x: "{0: >3}".format(x)
        minmax = lambda x: (min(x), max(x))
        clean_and_write(ALL_OBJECTS)
        write_title_screen(get_outfile(), get_seed(), get_flags())
        rewrite_snes_meta("FFMQ-R", VERSION, megabits=24, lorom=True)
        finish_interface()
    except Exception, e:
        print "ERROR: %s" % e
        raw_input("Press Enter to close this program.")
