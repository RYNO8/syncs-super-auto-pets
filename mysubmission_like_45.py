# print is buggy
print_original = print
print = lambda *args, **kwargs: print_original(*args, **{**kwargs, "flush": True})

from itertools import permutations, chain, combinations, count
from collections import defaultdict
from enum import Enum
from copy import copy, deepcopy
from math import ceil
from typing import List, Optional, Tuple, Dict
import shutil
import sys
from traceback import TracebackException
from json import dumps, loads, dump
from signal import SIGALRM, alarm, signal
from time import time
from random import sample, choice, randint, shuffle
import os

from submissionhelper.info.otherplayerpetinfo import OtherPlayerPetInfo
from submissionhelper.info.pettype import PetType
from submissionhelper.info.playerpetinfo import PlayerPetInfo
from submissionhelper.info.foodtype import FoodType
from submissionhelper.info.shopfoodinfo import ShopFoodInfo
from submissionhelper.info.shoppetinfo import ShopPetInfo
from submissionhelper.botbattle import BotBattle
from submissionhelper.info.gameinfo import GameInfo





TIER_PETS = [
    [PetType.FISH, PetType.BEAVER, PetType.HORSE, PetType.PIG, PetType.ANT, PetType.MOSQUITO, PetType.CRICKET],
    [PetType.CRAB, PetType.SWAN, PetType.HEDGEHOG, PetType.FLAMINGO, PetType.KANGAROO, PetType.SPIDER, PetType.PEACOCK],
    [PetType.DODO, PetType.BADGER, PetType.DOLPHIN, PetType.GIRAFFE, PetType.ELEPHANT, PetType.CAMEL, PetType.BUNNY, PetType.DOG, PetType.SHEEP],
    [PetType.SKUNK, PetType.HIPPO, PetType.BISON, PetType.BLOWFISH, PetType.SQUIRREL, PetType.PENGUIN]
]
TIER_FOOD = [
    [FoodType.APPLE, FoodType.HONEY],
    [FoodType.MEAT_BONE, FoodType.CUPCAKE],
    [FoodType.SALAD_BOWL, FoodType.GARLIC],
    [FoodType.CANNED_FOOD, FoodType.PEAR]
]
NUM_PLAYERS = 5
STARTING_HEALTH = 10
STARTING_COINS = 10
PET_POSITIONS = 5
MAX_MOVES_PER_ROUND = 30
REROLL_COST = 1
LEVEL_2_CUTOFF = 2
LEVEL_3_CUTOFF = 5
PET_BUY_COST = 3
MAX_SHOP_TIER = 4
MAX_ROUNDS = 150


# Different abilities have different priority
#   - Battle abilities have a set order of execution that can be seen in the battle stage helper
#   - On-demand abilities are executed as soon as they are valid. If multiple on-demand abilities
#     should be executed for the same event, it is done in pet order
class AbilityType(Enum):
    # On-demand; triggers when a pet is bought from the shop
    BUY = 1 

    # On-demand; triggers when a pet is sold
    SELL = 2

    # On-demand; triggers when a pet is leveled up
    LEVEL_UP = 3 

    # Battle ability; triggers when a pet takes damage. Faint counts as hurt
    HURT = 4 

    # Battle ability; triggers when a friendly pet directly in front attacks
    # Note: ability attacks don't trigger this
    FRIEND_AHEAD_ATTACK = 5 

    # On-demand; triggers when the buy round starts
    BUY_ROUND_START = 6

    # Battle ability; triggers when the battle round starts
    BATTLE_ROUND_START = 7

    # On-demand; triggers when a friendly pet is summoned. Buy counts as summoned
    FRIEND_SUMMONED = 8

    # On-demand; triggers when a friend eats food
    FRIEND_ATE_FOOD = 9

    # Battle-ability; triggers before you attack an enemy
    BEFORE_ATTACK = 10

    # Battle-ability; triggers after you attack an enemy
    AFTER_ATTACK = 11

    # Battle-ability; triggers when you kill an enemy pet
    KNOCKOUT = 12

    # Battle-ability; triggers when the pet dies
    FAINTED = 13

    # On-demand; triggers when the buy round ends
    BUY_ROUND_END = 14

class PetConfig:
    def __init__(self,
                 pet_name,
                 tier,
                 base_attack,
                 base_health,
                 ability_type):
        self.PET_NAME = pet_name
        self.TIER = tier
        self.BASE_HEALTH = base_health
        self.BASE_ATTACK = base_attack
        self.ABILITY_TYPE = ability_type

PET_CONFIG = {
    PetType.FISH: PetConfig(pet_name = "Fish",
                        tier = 1,
                        base_attack = 2,
                        base_health = 3,
                        ability_type = AbilityType.LEVEL_UP),

    PetType.BEAVER: PetConfig(pet_name = "Beaver",
                        tier = 1,
                        base_attack = 3,
                        base_health = 2,
                        ability_type= AbilityType.SELL),

    PetType.PIG: PetConfig(pet_name = "Pig",
                        tier = 1,
                        base_attack = 4,
                        base_health = 1,
                        ability_type = AbilityType.SELL),

    PetType.ANT: PetConfig(pet_name = "Ant",
                        tier = 1,
                        base_attack = 2,
                        base_health = 2,
                        ability_type= AbilityType.FAINTED),

    PetType.MOSQUITO: PetConfig(pet_name = "Mosquito",
                        tier = 1,
                        base_attack = 2,
                        base_health = 2,
                        ability_type= AbilityType.BATTLE_ROUND_START),

    PetType.CRICKET: PetConfig(pet_name = "Cricket",
                        tier = 1,
                        base_attack = 1,
                        base_health = 2,
                        ability_type= AbilityType.FAINTED),
    
    PetType.HORSE: PetConfig(pet_name = "Horse",
                        tier = 1,
                        base_attack = 2,
                        base_health = 1,
                        ability_type= AbilityType.FRIEND_SUMMONED),
    
    PetType.CRAB: PetConfig(pet_name = "Crab",
                        tier = 2,
                        base_attack = 4,
                        base_health = 1,
                        ability_type= AbilityType.BATTLE_ROUND_START),
 
    PetType.SWAN: PetConfig(pet_name = "Swan",
                        tier = 2,
                        base_attack = 1,
                        base_health = 2,
                        ability_type= AbilityType.BUY_ROUND_START),
    
    PetType.HEDGEHOG: PetConfig(pet_name = "Hedgehog",
                        tier = 2,
                        base_attack = 3,
                        base_health = 2,
                        ability_type= AbilityType.FAINTED),
    
    PetType.PEACOCK: PetConfig(pet_name = "Peacock",
                        tier = 2,
                        base_attack = 2,
                        base_health = 5,
                        ability_type= AbilityType.HURT),
    
    PetType.FLAMINGO: PetConfig(pet_name = "Flamingo",
                        tier = 2,
                        base_attack = 3,
                        base_health = 2,
                        ability_type= AbilityType.FAINTED),
    
    PetType.KANGAROO: PetConfig(pet_name = "Kangaroo",
                        tier = 2,
                        base_attack = 2,
                        base_health = 3,
                        ability_type= AbilityType.FRIEND_AHEAD_ATTACK),

    PetType.SPIDER: PetConfig(pet_name = "Spider",
                        tier = 2,
                        base_attack = 2,
                        base_health = 2,
                        ability_type= AbilityType.FAINTED),

    PetType.DODO: PetConfig(pet_name = "Dodo",
                        tier = 3,
                        base_attack = 4,
                        base_health = 2,
                        ability_type= AbilityType.BATTLE_ROUND_START),
    
    PetType.BADGER: PetConfig(pet_name = "Badger",
                        tier = 3,
                        base_attack = 6,
                        base_health = 3,
                        ability_type= AbilityType.FAINTED),
    
    PetType.DOLPHIN: PetConfig(pet_name = "Dolphin",
                        tier = 3,
                        base_attack = 4,
                        base_health = 3,
                        ability_type= AbilityType.BATTLE_ROUND_START),
    
    PetType.GIRAFFE: PetConfig(pet_name = "Giraffe",
                        tier = 3,
                        base_attack = 1,
                        base_health = 3,
                        ability_type= AbilityType.BUY_ROUND_END,),
    
    PetType.ELEPHANT: PetConfig(pet_name = "Elephant",
                        tier = 3,
                        base_attack = 3,
                        base_health = 7,
                        ability_type= AbilityType.AFTER_ATTACK),

    PetType.CAMEL: PetConfig(pet_name = "Camel",
                        tier = 3,
                        base_attack = 2,
                        base_health = 4,
                        ability_type= AbilityType.HURT),
    
    PetType.BUNNY: PetConfig(pet_name = "Bunny",
                        tier = 3,
                        base_attack = 1,
                        base_health = 2,
                        ability_type= AbilityType.FRIEND_ATE_FOOD),

    PetType.DOG: PetConfig(pet_name = "Dog",
                        tier = 3,
                        base_attack = 2,
                        base_health = 3,
                        ability_type= AbilityType.FRIEND_SUMMONED),

    PetType.SHEEP: PetConfig(pet_name = "Sheep",
                        tier = 3,
                        base_attack = 2,
                        base_health = 2,
                        ability_type= AbilityType.FAINTED),

    PetType.SKUNK: PetConfig(pet_name = "Skunk",
                        tier = 4,
                        base_attack = 3,
                        base_health = 5,
                        ability_type= AbilityType.BATTLE_ROUND_START),

    PetType.HIPPO: PetConfig(pet_name = "Hippo",
                        tier = 4,
                        base_attack = 4,
                        base_health = 5,
                        ability_type= AbilityType.KNOCKOUT),

    PetType.BISON: PetConfig(pet_name = "Bison",
                        tier = 4,
                        base_attack = 4,
                        base_health = 4,
                        ability_type= AbilityType.BUY_ROUND_END),

    PetType.BLOWFISH: PetConfig(pet_name = "Blowfish",
                        tier = 4,
                        base_attack = 3,
                        base_health = 6,
                        ability_type= AbilityType.HURT),

    PetType.SQUIRREL: PetConfig(pet_name = "Squirrel",
                        tier = 4,
                        base_attack = 2,
                        base_health = 5,
                        ability_type= AbilityType.BUY_ROUND_START),

    PetType.PENGUIN: PetConfig(pet_name = "Penguin",
                        tier = 4,
                        base_attack = 2,
                        base_health = 4,
                        ability_type= AbilityType.BUY_ROUND_END),

    PetType.BEE: PetConfig(pet_name = "Bee",
                        tier = None,
                        base_attack = 1,
                        base_health = 1,
                        ability_type= None),

    PetType.RAM: PetConfig(pet_name = "Ram",
                        tier = None,
                        base_attack = None,
                        base_health = None,
                        ability_type= None),

    PetType.ZOMBIE_CRICKET: PetConfig(pet_name = "Zombie Cricket",
                        tier = None,
                        base_attack = None,
                        base_health = None,
                        ability_type= None),
}



def powerset(iterable):
    "powerset([1,2,3]) --> () (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)"
    s = list(iterable)
    return chain.from_iterable(combinations(s, r) for r in range(len(s)+1))

def getSublevel(*pets):
    total = 0
    for pet in pets:
        if isinstance(pet, PlayerPetInfo):
            total += pet.sub_level + LEVEL_2_CUTOFF * (pet.level == 2) + LEVEL_3_CUTOFF * (pet.level == 3)
        else:
            total += 0
    return total + len(pets) - 1

PlayerPetInfo.__repr__ = PlayerPetInfo.__str__ = ShopPetInfo.__repr__ = ShopPetInfo.__str__ = lambda self: f"{str(self.type)[8:]}={getSublevel(self)} {self.health}/{self.attack}"
ShopFoodInfo.__repr__ = ShopFoodInfo.__str__ = lambda self: str(self.type)[9:]

# Core class for the submission helper
# Use this to make moves and get game info
bot_battle = BotBattle()
G: GameInfo = bot_battle.get_game_info()

def getPet(pet):
    id = pet.id
    for pet in G.player_info.pets:
        if pet and pet.id == id: return pet
    for pet in G.player_info.shop_pets:
        if pet.id == id: return pet
    raise IndexError

def getFood(food):
    id = food.id
    for food in G.player_info.shop_foods:
        if food.id == id: return food
    raise IndexError

def collectPets(type: PetType):
    return [pet for pet in G.player_info.pets if pet and pet.type == type]

def availableTypes():
    if G.round_num < 3:
        tier = 1
    elif G.round_num < 5:
        tier = 2
    elif G.round_num < 7:
        tier = 3
    else:
        tier = 4
    out = []
    for available in TIER_PETS[:tier]:
        out += available
    return [str(t)[8:] for t in out]

def get_level(sub_level: int) -> int:
    if sub_level == LEVEL_3_CUTOFF:
        return 3
    elif sub_level >= LEVEL_2_CUTOFF:
        return 2
    else:
        return 1

################################################################################
################################################################################

# approximation of HA stats at round `final_round`
def petMetric(pet: Optional[ShopPetInfo]) -> float:
    if pet is None:
        return 0
    if pet.type in [PetType.BADGER]:
        return -1000000
    
    final_round = max(6, min(13, G.round_num + 5))
    
    opps = [opp for opp in G.next_opponent_info.pets if opp]
    if opps:
        num_hits = max(
            min(ceil(opp.health / pet.attack), ceil(pet.health / opp.attack))
            for opp in opps
        )
    else:
        num_hits = 0
    
    level = pet.level if isinstance(pet, PlayerPetInfo) else 1
    health = pet.health
    attack = pet.attack
    adjust = 0
    
    if isinstance(pet, PlayerPetInfo) and pet.carried_food:
        # Non-ability attacks will now deal +3 damage
        if pet.carried_food == FoodType.MEAT_BONE:
            if pet.health >= 3:
                attack += 3
            # adjust += health * (attack + 3) - health * attack
        # Pet will take 2 less damage from all sources
        elif pet.carried_food == FoodType.GARLIC:
            num_hits = 2
            health += 2 * num_hits
            # adjust += (health + 2 * num_hits) * attack - health * attack
        elif pet.carried_food == FoodType.HONEY:
            adjust += 1 * 1
        elif pet.carried_food == FoodType.PEAR:
            health += 2
            attack += 2
            # adjust += (health + 2) * (attack + 2) - (health * attack)
            
    # Give 2 (random) pets +1L health and +1L attack
    if pet.type == PetType.FISH:
        adjust += (2 / 5) * (2 / 5)
        
    # Gain 0.5L health from the healthiest friend
    elif pet.type == PetType.CRAB:
        # safe to be accessing G.player_info.pets?
        final_max_health = max(pet.health for pet in G.player_info.pets if pet)
        # final_max_health = 5
        health += (level * final_max_health) // 2
        
    # If this has a level 3 friend, gain L attack and 2L health
    elif pet.type == PetType.BISON:
        if any(pet and getSublevel(pet) >= 4 for pet in G.player_info.pets):
            attack += level * (final_round - G.round_num)
            health += 2 * level * (final_round - G.round_num)
        print(health, attack, adjust)
        
    # Give nearest friend behind 2L attack and health
    elif pet.type == PetType.CAMEL:
        adjust += num_hits * (2 * level) * (2 * level)
        if collectPets(PetType.ELEPHANT):
            COEFF = 1.2
            adjust += COEFF * num_hits * (2 * level) * (2 * level)
    
    # Gain 3L health and attack
    elif pet.type == PetType.HIPPO:
        num_knockout = 1.1
        health += 3 * level * num_knockout
        attack += 3 * level * num_knockout
    
    # Gain 4L attack
    elif pet.type == PetType.PEACOCK:
        attack += num_hits * 1.5 * level
    
    return health * attack + adjust

def permMetric(pets: List[PlayerPetInfo], H=3, A=3):
    opp = [[H, A] for _ in range(100)]
    mine = deepcopy(pets)
    
    score = 0.001 * sum(pet.health * pet.attack * (5 - i) for i, pet in enumerate(mine))
    score += sum(pet[0] * pet[1] for pet in opp)
    
    # buy stage end - giraffe
    for i in range(len(mine)):
        if mine[i].type == PetType.GIRAFFE:
            for j in range(mine[i].level):
                if i - j - 1 >= 0:
                    mine[i - j - 1].health += 1
                    mine[i - j - 1].attack += 1
    
    for i in range(len(mine)):
        if mine[i].carried_food == FoodType.MEAT_BONE:
            mine[i].attack += 3
            
    while mine and opp:
        mine[0].health -= max(0, opp[0][1] - [0, 2][mine[0].carried_food == FoodType.GARLIC])
        opp[0][0] -= mine[0].attack
        
        # friend ahead attacks
        if 1 < len(mine) and mine[1].type == PetType.KANGAROO:
            mine[1].health += mine[1].level
            mine[1].attack += mine[1].level
            
        def doAbility(i):
            if i + 1 >= len(mine): return
            
            # hurt
            if mine[i].type == PetType.CAMEL and mine[i].health > 0:
                mine[i + 1].health += mine[i + 1].level * 2
                mine[i + 1].attack += mine[i + 1].level * 2
            
            if mine[i].type == PetType.ELEPHANT:
                for rep in range(mine[i].level):
                    mine[i + 1].health -= 1
                    if mine[i + 1].health <= 0:
                        mine.pop(i + 1)
                        if i + 1 >= len(mine): return
                    else:
                        doAbility(i + 1)
                    
        doAbility(0)
        
        # die
        if mine[0].health <= 0:
            mine.pop(0)
        if opp[0][0] <= 0:
            opp.pop(0)
    
    score -= sum(health * attack for health, attack in opp)
    return score

################################################################################
################################################################################

class Action:
    def __init__(self, docstring: str, score: float, succeed: List[callable], cost: int, fail: List[callable]):
        self.docstring = docstring
        self.score = score
        self.succeed = succeed
        self.cost = cost
        self.fail = fail
    
    def __str__(self):
        return f"({self.score}) {self.docstring}"
    
    def __repr__(self):
        return f"({self.score}) {self.docstring}"
    
    def __or__(self, other):
        return self if self.score >= other.score else other

    def __eq__(self, other):
        return self.docstring == other.docstring
    
    # assuming actions are independant
    def __and__(self, other):
        return Action(
            self.docstring + " & " + other.docstring,
            self.score + other.score,
            self.succeed + other.succeed,
            self.cost + other.cost,
            self.fail + other.fail
        )
    
    def exec(self, threshold = 1):
        if self.score >= threshold and G.player_info.coins >= self.cost:
            print(self)
            for f in self.succeed:
                f()
                globals()["G"] = bot_battle.get_game_info()
        elif self.score >= threshold:
            print("FREEZE", self)
            for f in self.fail:
                f()
                globals()["G"] = bot_battle.get_game_info()
    
    
    
    def nothing():
        return Action("NOTHING", 0, [], 0, [])
    
    def buy_pet(pet: ShopPetInfo, i: int):
        old = G.player_info.pets[i]
        return Action(
            f"INSERT {pet} {i}",
            petMetric(pet) - petMetric(old),
            ([lambda: bot_battle.sell_pet(getPet(old))] if old else []) + [lambda: bot_battle.buy_pet(getPet(pet), i)],
            2 if old else 3,
            [lambda: bot_battle.freeze_pet(getPet(pet))],
        )
    
    def level_pet_from_shop(pet_to_use: ShopPetInfo, pet_to_level_up: PlayerPetInfo):
        if pet_to_level_up.level == 3:
            return Action.nothing()
        
        leveled_up = deepcopy(pet_to_level_up)
        leveled_up.health = max(pet_to_level_up.health, pet_to_use.health) + 1
        leveled_up.attack = max(pet_to_level_up.attack, pet_to_use.attack) + 1
        leveled_up.sub_level += 1
        leveled_up.level = get_level(leveled_up.sub_level)
        
        return Action(
            f"UPGRADE {pet_to_use} {pet_to_level_up}",
            petMetric(leveled_up) - petMetric(pet_to_level_up),
            [lambda: bot_battle.level_pet_from_shop(getPet(pet_to_use), getPet(pet_to_level_up))],
            3,
            [lambda: bot_battle.freeze_pet(getPet(pet_to_use))],
        )
    
    def level_pet_from_pets(pet_to_use: ShopPetInfo, pet_to_level_up: PlayerPetInfo):
        if pet_to_level_up.level == 3:
            return Action.nothing()
        
        leveled_up = deepcopy(pet_to_level_up)
        leveled_up.health = max(pet_to_level_up.health, pet_to_use.health) + 1
        leveled_up.attack = max(pet_to_level_up.attack, pet_to_use.attack) + 1
        leveled_up.sub_level += pet_to_use.sub_level + 1
        leveled_up.level = get_level(leveled_up.sub_level)
        
        return Action(
            f"MERGE {pet_to_use} {pet_to_level_up}",
            petMetric(leveled_up) - petMetric(pet_to_level_up) - petMetric(pet_to_use), 
            [lambda: bot_battle.level_pet_from_pets(getPet(pet_to_use), getPet(pet_to_level_up))],
            0,
            [],
        )

    def buy_food(wanted_food: ShopFoodInfo, to_pet: PlayerPetInfo):
        fooded = deepcopy(to_pet)
        fooded.carried_food = wanted_food.type
        return Action(
            f"BUY FOOD {wanted_food} {to_pet}",
            petMetric(fooded) - petMetric(to_pet),
            [lambda: bot_battle.buy_food(getFood(wanted_food), getPet(to_pet))],
            3,
            [lambda: bot_battle.freeze_food(getFood(wanted_food))],
        )


################################################################################
################################################################################

# STAGE_* is `() -> bool`, which returns true immediately when it performs a move

def STAGE_perm():
    # try all permutations, chose best one
    best = -696969
    
    for perm in permutations(range(5)):
        pets = [G.player_info.pets[i] for i in perm if G.player_info.pets[i]]
        outcome = permMetric(pets, H=3, A=4) + permMetric(pets, H=1, A=1)
        if outcome > best:
            best = outcome
            bestPerm = perm
    
    print("SCORE IS", sum(petMetric(pet) for pet in G.player_info.pets))
    if best == -696969:
        print("STUPID ORDER!")
    else:
        print("WINNING ORDER IS", best)
        # print(G.player_info.pets)
        # print([G.player_info.pets[i] for i in bestPerm])
        bestPerm = list(bestPerm)
        # print(bestPerm)
        
        for i in range(5):
            if bestPerm[i] != i:
                # print("SWAP", bestPerm[i], i)
                bot_battle.swap_pets(bestPerm[i], i)
                globals()["G"] = bot_battle.get_game_info()
                j = bestPerm.index(i)
                k = i
                bestPerm[j], bestPerm[k] = bestPerm[k], bestPerm[j]
                
    print(G.player_info.pets)

def level_pet(pet_to_use, pet_to_level_up) -> Action:
    if pet_to_use in G.player_info.shop_pets:
        return Action.level_pet_from_shop(pet_to_use, pet_to_level_up)
    elif pet_to_level_up in G.player_info.shop_pets:
        return Action.level_pet_from_shop(pet_to_level_up, pet_to_use)
    else:
        assert pet_to_use in G.player_info.pets and pet_to_level_up in G.player_info.pets
        return Action.level_pet_from_pets(pet_to_use, pet_to_level_up)

def buy_insert(wanted_pet: ShopPetInfo) -> Action:
    action = Action.nothing()
    for i in range(5):
        action |= Action.buy_pet(wanted_pet, i)
    return action

def buy_merge(*pets: List[ShopPetInfo]) -> Action:
    if len(pets) < 2: return Action.nothing()
    pet_type = pets[0].type
    assert all(pet.type == pet_type for pet in pets)
    pets = sorted(pets, key=petMetric)
    
    action = Action.nothing()
    for to_merge in powerset(pets):
        if len(to_merge) >= 2 and getSublevel(*to_merge) <= 5:
            curr = Action.nothing()
            shop_pets = [pet for pet in to_merge if isinstance(pet, ShopPetInfo)]
            to_merge = [pet for pet in to_merge if isinstance(pet, PlayerPetInfo)]
            for pet in shop_pets + to_merge[:-1]:
                curr &= level_pet(pet, to_merge[-1])  # TODO: something broken here
            action |= curr
    return action

def find_best_action() -> Action:
    pets = [pet for pet in G.player_info.pets if pet]
    shop_pets = [shop_pet for shop_pet in G.player_info.shop_pets if shop_pet and not shop_pet.is_frozen]
    foods = [shop_food for shop_food in G.player_info.shop_foods if shop_food and not shop_food.is_frozen]
    
    action = Action.nothing()
    for wanted_pet in shop_pets:
        action |= buy_insert(wanted_pet)
        action |= buy_merge(wanted_pet, *collectPets(wanted_pet.type))
    for pet in pets:
        action |= buy_merge(*collectPets(pet.type))
    for to_pet in pets:
        for wanted_food in foods:
            if not to_pet.carried_food and wanted_food.type in [FoodType.MEAT_BONE, FoodType.GARLIC]:
                action |= Action.buy_food(wanted_food, to_pet)
    
    return action

def unfreeze():
    for pet in G.player_info.shop_pets:
        if pet.is_frozen:
            bot_battle.unfreeze_pet(getPet(pet))
            globals()["G"] = bot_battle.get_game_info()
    for food in G.player_info.shop_foods:
        if food.is_frozen:
            bot_battle.unfreeze_food(getFood(food))
            globals()["G"] = bot_battle.get_game_info()

def main():
    for round_num in count(1):
        # assert round_num == G.round_num
        print("#" * 20, G.round_num, "#" * 20)
        print()
        print(G.player_info.shop_pets, G.player_info.shop_foods)
        
        unfreeze()
        
        if G.round_num == 1:
            for _ in range(MAX_MOVES_PER_ROUND):
                find_best_action().exec(6)
                
            if sum(pet is not None for pet in G.player_info.pets) == 0:
                find_best_action().exec()
                
            bot_battle.reroll_shop()
            globals()["G"] = bot_battle.get_game_info()
            print(G.player_info.shop_pets, G.player_info.shop_foods)
            
            
            while sum(pet is not None for pet in G.player_info.pets) < 3 and G.player_info.coins >= 3:
                find_best_action().exec()
        
        while True:
            for _ in range(MAX_MOVES_PER_ROUND):
                # TODO: is 6 a good threshold?
                find_best_action().exec(6)
            
            if G.player_info.coins > 0:
                bot_battle.reroll_shop()
                globals()["G"] = bot_battle.get_game_info()
                print(G.player_info.shop_pets, G.player_info.shop_foods)
            else:
                break
        
        STAGE_perm()
        
        bot_battle.end_turn()
        globals()["G"] = bot_battle.get_game_info()
        print(flush = True)


if __name__ == "__main__":
    main()
