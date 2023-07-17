# print is buggy
print_original = print
print = lambda *args, **kwargs: print_original(*args, **{**kwargs, "flush": True})

from itertools import permutations, chain, combinations, count
from collections import defaultdict
from enum import Enum
from copy import copy, deepcopy
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
AVAILABLE: List[PetType] = []

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


################################################################################
################################################################################

def AHMetric(shop_pet: Optional[ShopPetInfo]):
    if shop_pet is None:
        return -696969
    AH = shop_pet.health * shop_pet.attack
    return AH

# TODO: but bison, hippo is better
def STRAT_ATTACK():
    out = [PetType.KANGAROO]
    if getSublevel(collectPets(PetType.FISH)) >= 2:
        out.append(PetType.FISH)
    if getSublevel(collectPets(PetType.BEAVER)) >= 2:
        out.append(PetType.BEAVER)
    return out

def STRAT_BUFFER():
    return [PetType.BUNNY, PetType.GIRAFFE]

def STRAT_HURT():
    return [PetType.CAMEL, PetType.ELEPHANT]

# do i want to KEEP this pet
def petMetric(pet: ShopPetInfo):
    if getSublevel(*collectPets(pet.type)) == 5: # this pet is lvl 3, useful
        return +1
    elif G.round_num < 5:
        # rating = {
        #     # tier 1
        #     PetType.HORSE: -3,
        #     PetType.ANT: +4,
        #     PetType.FISH: +2,
        #     PetType.PIG: -1,
        #     PetType.BEAVER: +1,
        #     PetType.MOSQUITO: +3,
        #     PetType.CRICKET: -6,
        # }
        rating = {
            # tier 1
            PetType.FISH: +2,
            PetType.BEAVER: +2,
        }
        return rating.get(pet.type, -1)
    else:
        if pet.type in STRAT_ATTACK() + STRAT_BUFFER() + STRAT_HURT():
            return 2 + PET_CONFIG[pet.type].TIER / 10
        elif getSublevel(pet) >= 2:
            return +1
        else:
            return -1

# do i want to BUY this pet?
# all shop pets you definitely want to buy, sorted
def shopPetsMetric():
    if G.round_num <= 2:
        filtered = []
        for pet in G.player_info.shop_pets:
            if petMetric(pet) <= 0: continue
            filtered.append(pet)
        return sorted(filtered, key=petMetric, reverse=True)
    
    else:
        filtered = []
        for pet in G.player_info.shop_pets:
            sublevel = getSublevel(*collectPets(pet.type))
            if sublevel >= 5: continue
            # no way i can get to lvl 3 with rare pets
            elif pet.type in STRAT_ATTACK() + STRAT_HURT() and sublevel >= 2: continue
            elif pet.type in STRAT_BUFFER() and sublevel >= 1: continue
            elif petMetric(pet) <= 0: continue
            filtered.append(pet)
        return sorted(filtered, key=petMetric, reverse=True)

def foodMetric():
    pets = [pet for pet in G.player_info.pets if pet]
    foods = G.player_info.shop_foods
    
    best_score = 0
    best_assignment = []
    
    def tryAssignment(assignment: List[Tuple[ShopFoodInfo, PlayerPetInfo]]):
        score = 0
        received = {}
        for pet in G.player_info.pets:
            if pet and pet.carried_food:
                received[pet.id] = pet.carried_food
                
        for food, pet in assignment[::-1]:
            if food.type == FoodType.CANNED_FOOD:
                score += sum(AHMetric(i) for i in pets) / len(pets)
                continue

            # if collectPets(PetType.BUNNY) or not pet.carried_food:
            if pet.id not in received:
                if food.type == FoodType.MEAT_BONE and pet.type in STRAT_ATTACK():
                    score += AHMetric(pet)
                elif food.type == FoodType.GARLIC and pet.type in STRAT_HURT():
                    score += AHMetric(pet)
            if pet.id not in received:
                received[pet.id] = food.type
                
        nonlocal best_score, best_assignment
        if score > best_score:
            best_score = score
            best_assignment = assignment
    
    for pet_a in pets:
        tryAssignment([(foods[0], pet_a)])
        if len(foods) >= 2: tryAssignment([(foods[1], pet_a)])
        for pet_b in pets:
            if G.player_info.coins < 6: continue
            if len(foods) >= 2: tryAssignment([(foods[0], pet_a), (foods[1], pet_b)])
            if len(foods) >= 2: tryAssignment([(foods[1], pet_a), (foods[0], pet_b)])
            
    return best_assignment

def permMetric(pets: List[PlayerPetInfo]):
    opp = [[3, 3] for _ in range(100)]
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

# STAGE_* is `() -> bool`, which returns true immediately when it performs a move

################################################################################
################################################################################

def STAGE_perm():
    # try all permutations, chose best one
    best = -696969
    
    for perm in permutations(range(5)):
        outcome = permMetric([G.player_info.pets[i] for i in perm if G.player_info.pets[i]])
        if outcome > best:
            best = outcome
            bestPerm = perm
    
    if best == -696969:
        print("STUPID ORDER!")
    else:
        print("WINNING ORDER IS", best)
        print(G.player_info.pets)
        print([G.player_info.pets[i] for i in bestPerm])
        bestPerm = list(bestPerm)
        print(bestPerm)
        
        for i in range(5):
            if bestPerm[i] != i:
                # print("SWAP", bestPerm[i], i)
                bot_battle.swap_pets(bestPerm[i], i)
                globals()["G"] = bot_battle.get_game_info()
                j = bestPerm.index(i)
                k = i
                bestPerm[j], bestPerm[k] = bestPerm[k], bestPerm[j]
                
    print(globals()["G"].player_info.pets)

def STAGE_buy_insert(wanted_pet: ShopPetInfo):
    if None in G.player_info.pets:
        i = G.player_info.pets.index(None)
        print("INSERT", wanted_pet.type, i)
        bot_battle.buy_pet(getPet(wanted_pet), i)
        globals()["G"] = bot_battle.get_game_info()
        return True
    return False

def level_pet(pet_to_use, pet_to_level_up):
    if pet_to_use in G.player_info.shop_pets:
        bot_battle.level_pet_from_shop(pet_to_use, pet_to_level_up)
    elif pet_to_level_up in G.player_info.shop_pets:
        bot_battle.level_pet_from_shop(pet_to_level_up, pet_to_use)
    else:
        assert pet_to_use in G.player_info.pets and pet_to_level_up in G.player_info.pets
        bot_battle.level_pet_from_pets(pet_to_use, pet_to_level_up)

def STAGE_buy_merge_any(*pets: List[ShopPetInfo]):
    if len(pets) < 2: return False
    pet_type = pets[0].type
    assert all(pet.type == pet_type for pet in pets)
    if not pets or pet_type == PetType.BUNNY: return False
    pets = sorted(pets, key=AHMetric)

    print("MERGE", pet_type)
    # merge smallest pet into biggest pet
    level_pet(getPet(pets[0]), getPet(pets[-1]))
    globals()["G"] = bot_battle.get_game_info()
    return True

def STAGE_buy_merge_all(*pets: List[ShopPetInfo]):
    if len(pets) < 2: return False
    pet_type = pets[0].type
    assert all(pet.type == pet_type for pet in pets)
    if not pets or pet_type == PetType.BUNNY: return False
    pets = sorted(pets, key=AHMetric)

    for pet in pets[:-1]:
        level_pet(getPet(pet), getPet(pets[-1]))
        globals()["G"] = bot_battle.get_game_info()
    return True

def STAGE_buy_merge_level(*pets: List[ShopPetInfo]):
    if len(pets) < 2: return False
    pet_type = pets[0].type
    assert all(pet.type == pet_type for pet in pets)
    if not pets or pet_type == PetType.BUNNY: return False
    pets = sorted(pets, key=AHMetric)
    
    for to_merge in powerset(pets):
        if len(to_merge) >= 2 and getSublevel(*to_merge) in [2, 5]:
            return STAGE_buy_merge_all(*to_merge)
    return False

def STAGE_buy_exchange(wanted_pet: ShopPetInfo):
    best = (6969, 6969)
    for i, pet in enumerate(G.player_info.pets):
        if pet and (petMetric(pet), AHMetric(pet)) < best:
            best = (petMetric(pet), AHMetric(pet))
            to_sell = i
    assert best != 6969
    
    if best[0] < 0 < petMetric(wanted_pet):
        print("EXCHANGE", getPet(G.player_info.pets[to_sell]), getPet(wanted_pet), to_sell)
        bot_battle.sell_pet(getPet(G.player_info.pets[to_sell]))
        globals()["G"] = bot_battle.get_game_info()
        bot_battle.buy_pet(getPet(wanted_pet), to_sell)
        globals()["G"] = bot_battle.get_game_info()
        return True
    else:
        return False

def STAGE_freeze_pets():
    for wanted_pet in shopPetsMetric():
        if not wanted_pet.is_frozen:
            print("FREEZE PET", wanted_pet)
            bot_battle.freeze_pet(getPet(wanted_pet))
            globals()["G"] = bot_battle.get_game_info()
    return False

def STAGE_buy_pet():
    if G.player_info.coins < 3: return False
    
    for wanted_pet in shopPetsMetric():
        if STAGE_buy_insert(wanted_pet):
            return True
        if STAGE_buy_exchange(wanted_pet):
            return True
        if STAGE_buy_merge_any(wanted_pet, *collectPets(wanted_pet.type)):
            return True
        if any(pet and STAGE_buy_merge_any(*collectPets(pet.type)) for pet in G.player_info.pets) and STAGE_buy_insert(wanted_pet):
            return True
        print(f"cannot insert {wanted_pet}")
    return False

def STAGE_freeze_food():
    for food in G.player_info.shop_foods:
        if food.type in [FoodType.MEAT_BONE, FoodType.GARLIC] and not food.is_frozen:
            print("FREEZE FOOD", food)
            bot_battle.freeze_food(food)
            globals()["G"] = bot_battle.get_game_info()
            return True
    return False

def STAGE_buy_foods():
    if G.player_info.coins < 3: return False

    for wanted_food, to_pet in foodMetric():
        print("BUY FOOD", getFood(wanted_food), getPet(to_pet))
        bot_battle.buy_food(getFood(wanted_food), getPet(to_pet))
        globals()["G"] = bot_battle.get_game_info()
    return False

def STAGE_unfreeze():
    for pet in G.player_info.shop_pets:
        if pet.is_frozen:
            bot_battle.unfreeze_pet(getPet(pet))
            globals()["G"] = bot_battle.get_game_info()
    for food in G.player_info.shop_foods:
        if food.is_frozen:
            bot_battle.unfreeze_food(getFood(food))
            globals()["G"] = bot_battle.get_game_info()
    return False

def main():
    for round_num in count(1):
        assert round_num == G.round_num
        print("#" * 20, G.round_num, "#" * 20)
        print()
        print(G.player_info.shop_pets, G.player_info.shop_foods)
        globals()["AVAILABLE"] = availableTypes()
        
        STAGE_unfreeze()
        
        if G.round_num == 1:
            while STAGE_buy_pet(): continue
            if sum(pet is not None for pet in G.player_info.pets) == 0:
                success = STAGE_buy_insert(max(G.player_info.shop_pets, key=AHMetric))
                assert success
                
            bot_battle.reroll_shop()
            globals()["G"] = bot_battle.get_game_info()
            print(G.player_info.shop_pets, G.player_info.shop_foods)
            
            
            while STAGE_buy_pet(): continue
            while sum(pet is not None for pet in G.player_info.pets) < 3 and G.player_info.coins >= 3:
                # first round, make sure you have 3 pets so you dont lose a health
                success = STAGE_buy_insert(max(G.player_info.shop_pets, key=AHMetric))
                assert success
                
            assert sum(pet is not None for pet in G.player_info.pets) == 3
        
        if G.round_num >= 3:
            STAGE_buy_merge_level(*collectPets(PetType.FISH))
            STAGE_buy_merge_level(*collectPets(PetType.BEAVER))
                
        while True:
            while STAGE_buy_pet(): continue
            if G.round_num >= 3:
                STAGE_buy_merge_level(*collectPets(PetType.FISH))
                STAGE_buy_merge_level(*collectPets(PetType.BEAVER))
            if G.round_num >= 3:
                STAGE_buy_foods()
            STAGE_freeze_pets()
            while STAGE_freeze_food(): continue
            
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
