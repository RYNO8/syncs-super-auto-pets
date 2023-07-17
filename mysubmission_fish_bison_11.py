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

class FoodConfig:
    def __init__(self,
                 food_name,
                 tier,
                 buy_cost,
                 is_targeted,
                 is_carried,
                 effect_func,):
        self.FOOD_NAME = food_name
        self.TIER = tier
        self.BUY_COST = buy_cost
        self.IS_TARGETED = is_targeted
        self.IS_CARRIED = is_carried
        self.EFFECT_FUNC = effect_func
class FoodEffects:
    @staticmethod
    def apple_effect(pet: 'PetState', player: 'PlayerState', state: 'GameState'):
        pet.perm_increase_health(1)
        pet.perm_increase_attack(1)
        player.friend_ate_food(pet)
    @staticmethod
    def cupcake_effect(pet: 'PetState', player: 'PlayerState', state: 'GameState'):
        pet.change_health(3)
        pet.change_attack(3)
        player.friend_ate_food(pet)
    @staticmethod
    def salad_bowl_effect(unused: 'PetState', player: 'PlayerState', state: 'GameState'):
        pets = [pet for pet in player.pets if pet is not None]
        num_choose = min(len(pets), 2)
        pets_to_upgrade = sample(pets, num_choose)
        for pet in pets_to_upgrade:
            pet.perm_increase_health(1)
            pet.perm_increase_attack(1)
            player.friend_ate_food(pet)
    @staticmethod
    def canned_food_effect(unused: 'PetState', player: 'PlayerState', state: 'GameState'):
        player.shop_perm_health_bonus += 1
        player.shop_perm_attack_bonus += 1
    @staticmethod
    def pear_effect(pet: 'PetState', player: 'PlayerState', state: 'GameState'):
        pet.perm_increase_health(2)
        pet.perm_increase_attack(2)
        player.friend_ate_food(pet)
FOOD_CONFIG = {
    FoodType.APPLE: FoodConfig(food_name = "Apple",
                            tier = 1,
                            buy_cost = 3,
                            is_targeted = True,
                            is_carried = False,
                            effect_func = FoodEffects.apple_effect),
    FoodType.HONEY: FoodConfig(food_name = "Honey",
                            tier = 1,
                            buy_cost = 3,
                            is_targeted = True,
                            is_carried = True,
                            effect_func = None),
    FoodType.MEAT_BONE: FoodConfig(food_name = "Meat Bone",
                            tier = 2,
                            buy_cost = 3,
                            is_targeted = True,
                            is_carried = True,
                            effect_func = None),
    FoodType.CUPCAKE: FoodConfig(food_name = "Cupcake",
                            tier = 2,
                            buy_cost = 3,
                            is_targeted = True,
                            is_carried = False,
                            effect_func = FoodEffects.cupcake_effect),
    FoodType.SALAD_BOWL: FoodConfig(food_name = "Salad Bowl",
                            tier = 3,
                            buy_cost = 3,
                            is_targeted = False,
                            is_carried = False,
                            effect_func = FoodEffects.salad_bowl_effect),
    FoodType.GARLIC: FoodConfig(food_name = "Garlic",
                            tier = 3,
                            buy_cost = 3,
                            is_targeted = True,
                            is_carried = True,
                            effect_func = None),
    FoodType.CANNED_FOOD: FoodConfig(food_name = "Canned Food",
                            tier = 4,
                            buy_cost = 3,
                            is_targeted = False,
                            is_carried = False,
                            effect_func = FoodEffects.canned_food_effect),
    FoodType.PEAR: FoodConfig(food_name = "Pear",
                            tier = 4,
                            buy_cost = 3,
                            is_targeted = True,
                            is_carried = False,
                            effect_func = FoodEffects.pear_effect),
}
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
CORE_DIRECTORY = os.environ["GAME_ENGINE_CORE_DIRECTORY"] if "GAME_ENGINE_CORE_DIRECTORY" in os.environ else "."
OPEN_PIPE_TIMEOUT_SECONDS = 1
WRITE_PIPE_TIMEOUT_SECONDS = 1
READ_PIPE_TIMEOUT_SECONDS = 1
CUMULATIVE_MAX_TIME = 2.5
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
# Abilities are scaled per level, where L = level
class PetAbilities:
    @staticmethod
    # On level up, Give 2 (random) pets +1L health and +1L attack
    def fish_ability(fish: 'PetState', player: 'PlayerState'):
        other_pets = [pet for pet in player.pets if pet != fish and pet is not None]
        num_choose = min(len(other_pets), 2)
        pets_to_upgrade = sample(other_pets, num_choose)
        for pet in pets_to_upgrade:
            pet.perm_increase_health(fish.get_level() - 1)
            pet.perm_increase_attack(fish.get_level() - 1)
    @staticmethod
    # On sell, give L gold
    def pig_ability(pig: 'PetState', player: 'PlayerState'):
        level = pig.get_level()
        player.coins += level
    @staticmethod
    # On sell, give 2 (random) pets +L attack
    def beaver_ability(beaver: 'PetState', player: 'PlayerState'):
        other_pets = [pet for pet in player.pets if pet != beaver and pet is not None]
        num_choose = min(len(other_pets), 2)
        pets_to_upgrade = sample(other_pets, num_choose)
        for pet in pets_to_upgrade:
            pet.perm_increase_attack(beaver.get_level())
    @staticmethod
    # On faint, give L attack and health to a random friend
    def ant_ability(ant: 'PetState', player: 'PlayerState'):
        other_pets = [pet for pet in player.battle_pets if pet != ant and pet is not None]
        # If there are no other pets we're done
        if len(other_pets) == 0: return
        pet_to_upgrade = choice(other_pets)
        pet_to_upgrade.change_attack(ant.get_level())
        pet_to_upgrade.change_health(ant.get_level())
    @staticmethod
    # At start of battle, deal 1 damage to L enemies
    def mosquito_ability(mosquito: 'PetState', player: 'PlayerState'):
        targets = player.opponent.battle_pets
        num_choose = min(len(targets), mosquito.get_level())
        pets_to_snipe = sample(targets, num_choose)
        for pet in pets_to_snipe:
            mosquito.damage_enemy_with_ability(1, pet)
    @staticmethod
    # On faint, spawn a zombie cricket with L attack and health
    def cricket_ability(cricket: 'PetState', player: 'PlayerState'):
        zombie_cricket = player.create_pet_to_summon(PetType.ZOMBIE_CRICKET, cricket.get_level(), cricket.get_level())
        player.summon_pets(cricket, [zombie_cricket])
    @staticmethod
    # Friend summoned, give L attack until the end of combat
    def horse_ability(horse: 'PetState', player: 'PlayerState'):
        player.new_summoned_pet.change_attack(horse.get_level())
    @staticmethod
    # Start of combat, gain 0.5L health from the healthiest friend
    def crab_ability(crab: 'PetState', player: 'PlayerState'):
        highest_health = max([pet.get_health() for pet in player.pets if pet != crab and pet is not None])
        crab.change_health(int(0.5 * highest_health * crab.get_level()))
    @staticmethod
    # Start of turn (buy period), gain L gold
    def swan_ability(swan: 'PetState', player: 'PlayerState'):
        level = swan.get_level()
        player.coins += level
    @staticmethod
    # On faint, deal 2L damage to all
    def hedgehog_ability(hedgehog: 'PetState', player: 'PlayerState'):
        for pet in player.battle_pets + player.opponent.battle_pets:
            hedgehog.damage_enemy_with_ability(2 * hedgehog.get_level(), pet)
    @staticmethod
    # When hurt, gain 4L attack
    def peacock_ability(peacock: 'PetState', player: 'PlayerState'):
        peacock.change_attack(4 * peacock.get_level())
    @staticmethod
    # Friend ahead attacks, gain L health and damage
    def kangaroo_ability(kangaroo: 'PetState', player: 'PlayerState'):
        kangaroo.change_attack(kangaroo.get_level())
        kangaroo.change_health(kangaroo.get_level())
    @staticmethod
    # On faint, give L health and attack to two nearest pets behind
    def flamingo_ability(flamingo: 'PetState', player: 'PlayerState'):
        index = player.battle_pets.index(flamingo)
        if len(player.battle_pets) > index + 1:
            player.battle_pets[index + 1].change_attack(flamingo.get_level())
            player.battle_pets[index + 1].change_health(flamingo.get_level())
        if len(player.battle_pets) > index + 2:
            player.battle_pets[index + 2].change_attack(flamingo.get_level())
            player.battle_pets[index + 2].change_health(flamingo.get_level())
    @staticmethod
    # On faint, summon a tier 3 pet with 2L health and attack
    def spider_ability(spider: 'PetState', player: 'PlayerState'):
        pet_type = choice(TIER_PETS[3])
        pet = player.create_pet_to_summon(pet_type, 2 * spider.get_level(), 2 * spider.get_level())
        player.summon_pets(spider, [pet])
    @staticmethod
    # Start of battle, give 0.5L attack to the nearest friend ahead
    def dodo_ability(dodo: 'PetState', player: 'PlayerState'):
        dodo_index = player.battle_pets.index(dodo)
        if dodo_index != 0:
            player.battle_pets[dodo_index - 1].change_attack(int(0.5 * dodo.get_attack() * dodo.get_level()))
    @staticmethod
    # Before faint, deal 0.5L attack damage to the adjacent pets. Includes your own pets
    def badger_ability(badger: 'PetState', player: 'PlayerState'):
        attack = int(0.5 * badger.get_attack() * badger.get_level())
        index = player.battle_pets.index(badger)
        if index == 0:
            if len(player.opponent.battle_pets) > 0:
                badger.damage_enemy_with_ability(attack, player.opponent.battle_pets[0])
        else:
            badger.damage_enemy_with_ability(attack, player.battle_pets[index - 1])
        if len(player.battle_pets) > index + 1:
            badger.damage_enemy_with_ability(attack, player.battle_pets[index + 1])
    @staticmethod
    # Start of battle, deal 3 damage to the lowest health enemy. Triggers L times
    def dolphin_ability(dolphin: 'PetState', player: 'PlayerState'):
        for _ in range(dolphin.get_level()):
            pets = [pet for pet in player.opponent.battle_pets if pet.is_alive()]
            pets.sort(key = lambda pet: pet.get_health())
            if len(pets) > 0:
                dolphin.damage_enemy_with_ability(3, pets[0])
    @staticmethod
    # End of turn (buy phase), give 1 health and attack to L friends in front of it
    def giraffe_ability(giraffe: 'PetState', player: 'PlayerState'):
        pets = [pet for pet in player.pets if pet is not None]
        giraffe_index = pets.index(giraffe)
        # If it is at the front then no buffs can be given
        if giraffe_index == 0: return
        # The index will signify how many pets are in front of it (2nd place has index 1 and thus 1 pet infront)
        num_pets_to_buff = min(giraffe_index, giraffe.get_level())
        pets_to_buff = pets[(giraffe_index - num_pets_to_buff) : giraffe_index]
        for pet in pets_to_buff:
            pet.perm_increase_attack(1)
            pet.perm_increase_health(1)
    @staticmethod
    # When hurt, give nearest friend behind 2L attack and health
    def camel_ability(camel: 'PetState', player: 'PlayerState'):
        # If the camel has something behind it or is not yet the last pet
        if player.battle_pets[-1] != camel:
            buff_pet = player.battle_pets[player.battle_pets.index(camel) + 1]
            buff_pet.change_attack(2 * camel.get_level())
            buff_pet.change_health(2 * camel.get_level())
    @staticmethod
    # After attack, deal 1 damage to the friend behind L times
    def elephant_ability(elephant: 'PetState', player: 'PlayerState'):
        # Nothing will happen if it has no pet behind the elephant
        # Also covers case where it is just the elephant
        if player.battle_pets[-1] == elephant: return
        elephant_index = player.battle_pets.index(elephant)
        target_friend = player.battle_pets[elephant_index + 1]
        # Known bug: this wont retrigger other pets hurt ability multiple times
        for _ in range(elephant.get_level()):
            elephant.damage_enemy_with_ability(1, target_friend)
    @staticmethod
    # When a friendly eats food, give them +L health
    def bunny_ability(bunny: 'PetState', player: 'PlayerState'):
        target_friend = player.pet_that_ate_food
        target_friend.perm_increase_health(bunny.get_level())
    @staticmethod
    # When a friend is summoned, gain 2L attack and L health until end of battle (stacking and unlimited)
    def dog_ability(dog: 'PetState', player: 'PlayerState'):
        dog.change_health(dog.get_level())
        dog.change_attack(2 * dog.get_level())
    @staticmethod
    # On faint, summon 2 rams with 2L health and attack
    def sheep_ability(sheep: 'PetState', player: 'PlayerState'):
        stat = 2 * sheep.get_level()
        ram_a = player.create_pet_to_summon(PetType.RAM, stat, stat)
        ram_b = player.create_pet_to_summon(PetType.RAM, stat, stat)
        player.summon_pets(sheep, [ram_a, ram_b])
    @staticmethod
    # Battle round start -> Reduce the highest health enemy's health by 0.33*L
    def skunk_ability(skunk: 'PetState', player: 'PlayerState'):
        highest_health_pet = max(player.opponent.battle_pets, key = lambda pet: pet.get_health())
        percent = 0.33 * skunk.get_level()
        reduce_amount = int(highest_health_pet.get_health() * percent)
        highest_health_pet.change_health(-reduce_amount)
    @staticmethod
    # Knockout -> Gain 3L health and attack
    def hippo_ability(hippo: 'PetState', player: 'PlayerState'):
        hippo.change_health(3 * hippo.get_level())
        hippo.change_attack(3 * hippo.get_level())
    @staticmethod
    # End buy round -> If this has a level 3 friend, gain L attack and 2L health
    def bison_ability(bison: 'PetState', player: 'PlayerState'):
        level_3_friend = False
        for pet in player.pets:
            if pet is not None and pet.get_level() == 3:
                level_3_friend = True
                break
        if level_3_friend:
            bison.perm_increase_health(2 * bison.get_level())
            bison.perm_increase_attack(bison.get_level())
    @staticmethod
    # On hurt -> Deal 3L damage to one random enemy
    def blowfish_ability(blowfish: 'PetState', player: 'PlayerState'):
        if len(player.opponent.battle_pets) == 0: return
        target_pet = choice(player.opponent.battle_pets)
        blowfish.damage_enemy_with_ability(3 * blowfish.get_level(), target_pet)
    @staticmethod
    # Start of buy round -> discount all shop food by 1 coin
    def squirrel_ability(squirrel: 'PetState', player: 'PlayerState'):
        for food in player.shop_foods:
            food.cost -= squirrel.get_level()
            food.cost = max(0, food.cost)
    @staticmethod
    # End buy round -> Give two level 2+ friends L health and attack
    def penguin_ability(penguin: 'PetState', player: 'PlayerState'):
        strong_pets = [pet for pet in player.pets if pet != penguin and pet is not None and pet.get_level() >= 2]
        num_choose = min(len(strong_pets), 2)
        pets_to_upgrade = sample(strong_pets, num_choose)
        for pet in pets_to_upgrade:
            pet.perm_increase_health(penguin.get_level())
            pet.perm_increase_attack(penguin.get_level())
class PetConfig:
    def __init__(self,
                 pet_name,
                 tier,
                 base_attack,
                 base_health,
                 ability_type,
                 ability_func,):
        self.PET_NAME = pet_name
        self.TIER = tier
        self.BASE_HEALTH = base_health
        self.BASE_ATTACK = base_attack
        self.ABILITY_TYPE = ability_type
        self.ABILITY_FUNC = ability_func
PET_CONFIG = {
    PetType.FISH: PetConfig(pet_name = "Fish",
                        tier = 1,
                        base_attack = 2,
                        base_health = 3,
                        ability_type = AbilityType.LEVEL_UP,
                        ability_func = PetAbilities.fish_ability),
    PetType.BEAVER: PetConfig(pet_name = "Beaver",
                        tier = 1,
                        base_attack = 3,
                        base_health = 2,
                        ability_type= AbilityType.SELL,
                        ability_func= PetAbilities.beaver_ability),
    PetType.PIG: PetConfig(pet_name = "Pig",
                        tier = 1,
                        base_attack = 4,
                        base_health = 1,
                        ability_type = AbilityType.SELL,
                        ability_func = PetAbilities.pig_ability,),
    PetType.ANT: PetConfig(pet_name = "Ant",
                        tier = 1,
                        base_attack = 2,
                        base_health = 2,
                        ability_type= AbilityType.FAINTED,
                        ability_func= PetAbilities.ant_ability),
    PetType.MOSQUITO: PetConfig(pet_name = "Mosquito",
                        tier = 1,
                        base_attack = 2,
                        base_health = 2,
                        ability_type= AbilityType.BATTLE_ROUND_START,
                        ability_func= PetAbilities.mosquito_ability),
    PetType.CRICKET: PetConfig(pet_name = "Cricket",
                        tier = 1,
                        base_attack = 1,
                        base_health = 2,
                        ability_type= AbilityType.FAINTED,
                        ability_func= PetAbilities.cricket_ability),
    PetType.HORSE: PetConfig(pet_name = "Horse",
                        tier = 1,
                        base_attack = 2,
                        base_health = 1,
                        ability_type= AbilityType.FRIEND_SUMMONED,
                        ability_func= PetAbilities.horse_ability),
    PetType.CRAB: PetConfig(pet_name = "Crab",
                        tier = 2,
                        base_attack = 4,
                        base_health = 1,
                        ability_type= AbilityType.BATTLE_ROUND_START,
                        ability_func= PetAbilities.crab_ability),
    PetType.SWAN: PetConfig(pet_name = "Swan",
                        tier = 2,
                        base_attack = 1,
                        base_health = 2,
                        ability_type= AbilityType.BUY_ROUND_START,
                        ability_func= PetAbilities.swan_ability),
    PetType.HEDGEHOG: PetConfig(pet_name = "Hedgehog",
                        tier = 2,
                        base_attack = 3,
                        base_health = 2,
                        ability_type= AbilityType.FAINTED,
                        ability_func= PetAbilities.hedgehog_ability),
    PetType.PEACOCK: PetConfig(pet_name = "Peacock",
                        tier = 2,
                        base_attack = 2,
                        base_health = 5,
                        ability_type= AbilityType.HURT,
                        ability_func= PetAbilities.peacock_ability),
    PetType.FLAMINGO: PetConfig(pet_name = "Flamingo",
                        tier = 2,
                        base_attack = 3,
                        base_health = 2,
                        ability_type= AbilityType.FAINTED,
                        ability_func= PetAbilities.flamingo_ability),
    PetType.KANGAROO: PetConfig(pet_name = "Kangaroo",
                        tier = 2,
                        base_attack = 2,
                        base_health = 3,
                        ability_type= AbilityType.FRIEND_AHEAD_ATTACK,
                        ability_func= PetAbilities.kangaroo_ability),
    PetType.SPIDER: PetConfig(pet_name = "Spider",
                        tier = 2,
                        base_attack = 2,
                        base_health = 2,
                        ability_type= AbilityType.FAINTED,
                        ability_func= PetAbilities.spider_ability),
    PetType.DODO: PetConfig(pet_name = "Dodo",
                        tier = 3,
                        base_attack = 4,
                        base_health = 2,
                        ability_type= AbilityType.BATTLE_ROUND_START,
                        ability_func= PetAbilities.dodo_ability),
    PetType.BADGER: PetConfig(pet_name = "Badger",
                        tier = 3,
                        base_attack = 6,
                        base_health = 3,
                        ability_type= AbilityType.FAINTED,
                        ability_func= PetAbilities.badger_ability),
    PetType.DOLPHIN: PetConfig(pet_name = "Dolphin",
                        tier = 3,
                        base_attack = 4,
                        base_health = 3,
                        ability_type= AbilityType.BATTLE_ROUND_START,
                        ability_func= PetAbilities.dolphin_ability),
    PetType.GIRAFFE: PetConfig(pet_name = "Giraffe",
                        tier = 3,
                        base_attack = 1,
                        base_health = 3,
                        ability_type= AbilityType.BUY_ROUND_END,
                        ability_func= PetAbilities.giraffe_ability),
    PetType.ELEPHANT: PetConfig(pet_name = "Elephant",
                        tier = 3,
                        base_attack = 3,
                        base_health = 7,
                        ability_type= AbilityType.AFTER_ATTACK,
                        ability_func= PetAbilities.elephant_ability),
    PetType.CAMEL: PetConfig(pet_name = "Camel",
                        tier = 3,
                        base_attack = 2,
                        base_health = 4,
                        ability_type= AbilityType.HURT,
                        ability_func= PetAbilities.camel_ability),
    PetType.BUNNY: PetConfig(pet_name = "Bunny",
                        tier = 3,
                        base_attack = 1,
                        base_health = 2,
                        ability_type= AbilityType.FRIEND_ATE_FOOD,
                        ability_func= PetAbilities.bunny_ability),
    PetType.DOG: PetConfig(pet_name = "Dog",
                        tier = 3,
                        base_attack = 2,
                        base_health = 3,
                        ability_type= AbilityType.FRIEND_SUMMONED,
                        ability_func= PetAbilities.dog_ability),
    PetType.SHEEP: PetConfig(pet_name = "Sheep",
                        tier = 3,
                        base_attack = 2,
                        base_health = 2,
                        ability_type= AbilityType.FAINTED,
                        ability_func= PetAbilities.sheep_ability),
    PetType.SKUNK: PetConfig(pet_name = "Skunk",
                        tier = 4,
                        base_attack = 3,
                        base_health = 5,
                        ability_type= AbilityType.BATTLE_ROUND_START,
                        ability_func= PetAbilities.skunk_ability),
    PetType.HIPPO: PetConfig(pet_name = "Hippo",
                        tier = 4,
                        base_attack = 4,
                        base_health = 5,
                        ability_type= AbilityType.KNOCKOUT,
                        ability_func= PetAbilities.hippo_ability),
    PetType.BISON: PetConfig(pet_name = "Bison",
                        tier = 4,
                        base_attack = 4,
                        base_health = 4,
                        ability_type= AbilityType.BUY_ROUND_END,
                        ability_func= PetAbilities.bison_ability),
    PetType.BLOWFISH: PetConfig(pet_name = "Blowfish",
                        tier = 4,
                        base_attack = 3,
                        base_health = 6,
                        ability_type= AbilityType.HURT,
                        ability_func= PetAbilities.blowfish_ability),
    PetType.SQUIRREL: PetConfig(pet_name = "Squirrel",
                        tier = 4,
                        base_attack = 2,
                        base_health = 5,
                        ability_type= AbilityType.BUY_ROUND_START,
                        ability_func= PetAbilities.squirrel_ability),
    PetType.PENGUIN: PetConfig(pet_name = "Penguin",
                        tier = 4,
                        base_attack = 2,
                        base_health = 4,
                        ability_type= AbilityType.BUY_ROUND_END,
                        ability_func= PetAbilities.penguin_ability),
    PetType.BEE: PetConfig(pet_name = "Bee",
                        tier = None,
                        base_attack = 1,
                        base_health = 1,
                        ability_type= None,
                        ability_func= None),
    PetType.RAM: PetConfig(pet_name = "Ram",
                        tier = None,
                        base_attack = None,
                        base_health = None,
                        ability_type= None,
                        ability_func= None),
    PetType.ZOMBIE_CRICKET: PetConfig(pet_name = "Zombie Cricket",
                        tier = None,
                        base_attack = None,
                        base_health = None,
                        ability_type= None,
                        ability_func= None),
}
TIER_PETS = [
    [PetType.FISH, PetType.BEAVER, PetType.HORSE, PetType.PIG, PetType.ANT, PetType.MOSQUITO, PetType.CRICKET],
    [PetType.CRAB, PetType.SWAN, PetType.HEDGEHOG, PetType.FLAMINGO, PetType.KANGAROO, PetType.SPIDER, PetType.PEACOCK],
    [PetType.DODO, PetType.BADGER, PetType.DOLPHIN, PetType.GIRAFFE, PetType.ELEPHANT, PetType.CAMEL, PetType.BUNNY, PetType.DOG, PetType.SHEEP],
    [PetType.SKUNK, PetType.HIPPO, PetType.BISON, PetType.BLOWFISH, PetType.SQUIRREL, PetType.PENGUIN]
]
class RoundConfig:
    @staticmethod
    def get_round_config(round: int) -> 'RoundConfig':
        return ROUND_CONFIG[round] if round < len(ROUND_CONFIG) else ROUND_CONFIG[-1]
    def __init__(self,
                 round_num: int,
                 max_shop_tier: int,
                 num_shop_pets: int,
                 num_shop_foods: int,
                 health_lost: int):
        self.MAX_SHOP_TIER = max_shop_tier
        self.NUM_SHOP_PETS = num_shop_pets
        self.NUM_SHOP_FOODS = num_shop_foods
        self.HEALTH_LOST = health_lost
ROUND_CONFIG = [
    RoundConfig(round_num = 1,
                max_shop_tier = 1,
                num_shop_pets = 3,
                num_shop_foods = 1,
                health_lost = 1),
    RoundConfig(round_num = 2,
                max_shop_tier = 1,
                num_shop_pets = 3,
                num_shop_foods = 1,
                health_lost = 1),
    RoundConfig(round_num = 3,
                max_shop_tier = 2,
                num_shop_pets = 3,
                num_shop_foods = 1,
                health_lost = 2),
    RoundConfig(round_num = 4,
                max_shop_tier = 2,
                num_shop_pets = 3,
                num_shop_foods = 1,
                health_lost = 2),
    RoundConfig(round_num = 5,
                max_shop_tier = 3,
                num_shop_pets = 4,
                num_shop_foods = 2,
                health_lost = 2),
    RoundConfig(round_num = 6,
                max_shop_tier = 3,
                num_shop_pets = 4,
                num_shop_foods = 2,
                health_lost = 2),
    RoundConfig(round_num = 7,
                max_shop_tier = 4,
                num_shop_pets = 4,
                num_shop_foods = 2,
                health_lost = 3),
    RoundConfig(round_num = 8,
                max_shop_tier = 4,
                num_shop_pets = 4,
                num_shop_foods = 2,
                health_lost = 3),
    RoundConfig(round_num = 9,
                max_shop_tier = 4, # Real game this is 5
                num_shop_pets = 4,
                num_shop_foods = 2,
                health_lost = 3),
    RoundConfig(round_num = 10,
                max_shop_tier = 4, # Real game this is 5
                num_shop_pets = 4,
                num_shop_foods = 2,
                health_lost = 3),
    RoundConfig(round_num = 11,
                max_shop_tier = 4, # Real game this is 6
                num_shop_pets = 5,
                num_shop_foods = 2,
                health_lost = 3),
]
class GameLog:
    def __init__(self, state: 'GameState'):
        self.state = state
        # Per round, we store the starting state of each player
        self.start_state_logs: List[List[str]] = []
        # Per round, per player, we store the shop log + buy round moves
        self.buy_stage_logs: List[List[Tuple[bool, str, List[str]]]] = []
        # Per round, we store the outcomes of each battle
        self.battle_stage_logs: List[List[('PlayerState', str)]] = []
    def get_game_log(self, player: 'PlayerState') -> str:
        game_log = ""
        for round in range(self.state.round + 1):
            game_log += f"# Round {round + 1}\n\n"
            game_log += self._get_round_start_state_log(round, player)
            game_log += self._get_round_buy_stage_log(round, player)
            game_log += self._get_round_battle_stage_log(round, player)
        return game_log
    def write_start_state_logs(self):
        logs_per_player = []
        for player in self.state.players:
            log = ""
            if not player.is_alive():
                log += "- Eliminated"
            else:
                log += f"- {player.health} health remaining\n"
                for i, pet in enumerate(player.pets):
                    log += f"{i + 1}. {self._write_pet_log(pet)}\n"
            logs_per_player.append(log)
        self.start_state_logs.append(logs_per_player)
    def init_buy_stage_log(self):
        buy_stage_log = [(self.state.players[player_num].is_alive(), self._write_shop_log(self.state.players[player_num]), []) for player_num in range(NUM_PLAYERS)]
        self.buy_stage_logs.append(buy_stage_log)
    def write_buy_stage_log(self, player: 'PlayerState', log: str):
        _, _, logs = self.buy_stage_logs[self.state.round][player.player_num]
        logs.append(log)
    def init_battle_stage_log(self):
        self.battle_stage_logs.append([])
    def write_battle_stage_log(self, player: 'PlayerState', challenger: 'PlayerState', player_lost: Optional[bool], health_lost: int):
        log = ""
        if player_lost == True:
            log += f"P{player.player_num + 1} lost to P{challenger.player_num + 1}; "
            log += f"P{player.player_num + 1} lost {health_lost} health; "
            if player.is_alive():
                log += f"{player.health} health remaining"
            else:
                log += f"Eliminated"
        elif player_lost is None:
            log += f"P{player.player_num + 1} tied with P{challenger.player_num + 1}; "
            log += f"P{player.player_num + 1} has {player.health} health remaining"
        else:
            log += f"P{player.player_num + 1} beat P{challenger.player_num + 1}; "
            log += f"P{player.player_num + 1} has {player.health} health remaining"
        self.battle_stage_logs[self.state.round].append((player, log))
    def _get_round_start_state_log(self, round: int, player: 'PlayerState'):
        log = f"## Starting State\n\n"
        if round >= len(self.start_state_logs):
            log += f"Did not reach round {round + 1}\n\n"
            return log
        for player_num in range(NUM_PLAYERS):
            log += f"### "
            if player_num == player.player_num: log += "**"
            log += f"P{player_num + 1} "
            if player_num == player.player_num: log += "(self)** "
            round_start_log = self.start_state_logs[round][player_num]
            log += round_start_log
            log += "\n\n"
        return log
    def _get_round_buy_stage_log(self, round: int, player: 'PlayerState'):
        log = f"## Buy Stage\n"
        if round >= len(self.buy_stage_logs):
            log += f"Did not reach round {round + 1}\n\n"
            return log
        player_alive, shop_log, buy_logs = self.buy_stage_logs[round][player.player_num]
        # Return nothing if the player is already eliminated
        if not player_alive:
            return ""
        log += "### Shop\n"
        log += shop_log
        log += "\n"
        log += "### Moves\n"
        for i, buy_log in enumerate(buy_logs):
            log += f"{i + 1}. "
            log += buy_log
            log += "\n"
        log += "\n"
        return log
    def _get_round_battle_stage_log(self, round: int, player: 'PlayerState'):
        log = f"## Battle Stage\n"
        if round >= len(self.battle_stage_logs):
            log += f"Did not reach round {round + 1}\n\n"
            return log
        for _player, _log in self.battle_stage_logs[round]:
            log += "- "
            if _player == player: log += "**"
            log += _log
            if _player == player: log += "**"
            log += "\n"
        log += "\n"
        return log
    def _write_shop_log(self, player: 'PlayerState'):
        log = ""
        log += "Shop pets:\n"
        for i, pet in enumerate(player.shop_pets):
            log += f"{i + 1}. "
            log += f"\"{pet.pet_config.PET_NAME}\"; "
            log += f"{pet.get_perm_health()} health; "
            log += f"{pet.get_perm_attack()} attack\n"
        log += "\nShop foods:\n"
        for i, food in enumerate(player.shop_foods):
            log += f"{i + 1}. "
            log += f"\"{food.food_config.FOOD_NAME}\"\n"
        return log
    def _write_pet_log(self, pet: 'PetState') -> str:
        log = ""
        if pet is None:
            log += "None"
        else:
            log += f"\"{pet.pet_config.PET_NAME}\"; "
            log += f"{pet.get_perm_health()} health; "
            log += f"{pet.get_perm_attack()} attack; "
            log += f"Level {pet.get_level()}; "
            log += f"Sublevel progress {pet.get_sub_level_progress()}; "
            if pet.carried_food is None:
                log += f"No carried food"
            else:
                log += f"Carrying \"{pet.carried_food.FOOD_NAME}\""
        return log
class Battle:
    def __init__(self, player: 'PlayerState', challenger: 'PlayerState', state: 'GameState', log: 'GameLog'):
        self.player = player
        self.challenger = challenger
        self.state = state
        self.log = log
        self.hurt_and_faint_and_bee: List['PetState'] = []
        self.knockout: Optional['PetState'] = None
    def run(self):
        self._setup_battle()
        # End early if one of the players has no pets
        if len(self.player.battle_pets) == 0 or len(self.challenger.battle_pets) == 0:
            self._end_battle()
            return
        self._run_start_battle()
        while len(self.player.battle_pets) > 0 and len(self.challenger.battle_pets) > 0:
            self._run_attack_turn()
        self._end_battle()
    def add_hurt_or_fainted_or_bee(self, pet: 'PetState'):
        if pet not in self.hurt_and_faint_and_bee:
            self.hurt_and_faint_and_bee.append(pet)
    def _setup_battle(self):
        # Set opponent + create copy of pets (player.battle_pets)
        self.player.start_battle(self.challenger)
        self.challenger.start_battle(self.player)
        self._cleanup_battle_pets()
    def _run_start_battle(self):
        self._proc_battle_round_start()
        self._proc_hurt_and_faint()
        self._cleanup_battle_pets()
    def _run_attack_turn(self):
        self.hurt_and_faint_and_bee = []
        self.knockout = None
        player_front = self.player.battle_pets[0]
        challenger_front = self.challenger.battle_pets[0]
        self._proc_before_attack(player_front, challenger_front)
        player_front.damage_enemy_with_attack(challenger_front)
        challenger_front.damage_enemy_with_attack(player_front)
        self._add_to_knockout(player_front, challenger_front)
        self._proc_after_attack(player_front, challenger_front)
        self._proc_friend_ahead_attacked()
        self._proc_knockout()
        self._proc_hurt_and_faint()
        self._cleanup_battle_pets()
    def _end_battle(self):
        round_config = RoundConfig.get_round_config(self.state.round)
        player_lost = self._determine_winner()
        if player_lost:
            self.player.health -= round_config.HEALTH_LOST
        self.log.write_battle_stage_log(self.player, self.challenger, player_lost, round_config.HEALTH_LOST)
    # Remove dead pets and empty slots
    def _cleanup_battle_pets(self):
        self.player.battle_pets = [pet for pet in self.player.battle_pets if pet is not None and (pet.is_alive() or pet in self.hurt_and_faint_and_bee)]
        self.challenger.battle_pets = [pet for pet in self.challenger.battle_pets if pet is not None and (pet.is_alive() or pet in self.hurt_and_faint_and_bee)]
    # Higher level and stat pets get to go first
    def _priority_sort(self, pets: List['PetState']) -> List['PetState']:
        pets.sort(key = lambda pet: (pet.sub_level, pet.get_health() + pet.get_attack()), reverse = True)
        return pets
    def _determine_winner(self) -> bool:
        if len(self.player.battle_pets) == 0 and len(self.challenger.battle_pets) == 0:
            return None # Tied
        elif len(self.player.battle_pets) == 0:
            return True # Lost
        else:
            return False # Won
    def _proc_battle_round_start(self):
        battle_round_start: List['PetState'] = []
        battle_round_start += [pet for pet in self.player.battle_pets if pet.pet_config.ABILITY_TYPE == AbilityType.BATTLE_ROUND_START]
        battle_round_start += [pet for pet in self.challenger.battle_pets if pet.pet_config.ABILITY_TYPE == AbilityType.BATTLE_ROUND_START]
        for pet in self._priority_sort(battle_round_start):
            pet.pet_config.ABILITY_FUNC(pet, pet.player)
    def _proc_hurt_and_faint(self):
        while len(self.hurt_and_faint_and_bee) > 0:
            hurt_and_faint_and_bee = self._priority_sort(copy(self.hurt_and_faint_and_bee))
            self.hurt_and_faint_and_bee = [] # Clear the list so second-order events trigger
            for pet in hurt_and_faint_and_bee:
                if pet.pet_config.ABILITY_TYPE in [AbilityType.HURT, AbilityType.FAINTED]:
                    pet.pet_config.ABILITY_FUNC(pet, pet.player)
                if not pet.is_alive() and pet.carried_food == FOOD_CONFIG[FoodType.HONEY]:
                    pet.player.summon_bee(pet)
            self._cleanup_battle_pets()
    def _proc_before_attack(self, player_front: 'PetState', challenger_front: 'PetState'):
        before_attack: List['PetState'] = []
        if player_front.pet_config.ABILITY_TYPE == AbilityType.BEFORE_ATTACK:
            before_attack.append(player_front)
        if challenger_front.pet_config.ABILITY_TYPE == AbilityType.BEFORE_ATTACK:
            before_attack.append(challenger_front)
        for pet in self._priority_sort(before_attack):
            pet.pet_config.ABILITY_FUNC(pet, pet.player)
    def _proc_after_attack(self, player_front: 'PetState', challenger_front: 'PetState'):
        after_attack: List['PetState'] = []
        if player_front.pet_config.ABILITY_TYPE == AbilityType.AFTER_ATTACK:
            after_attack.append(player_front)
        if challenger_front.pet_config.ABILITY_TYPE == AbilityType.AFTER_ATTACK:
            after_attack.append(challenger_front)
        for pet in self._priority_sort(after_attack):
            pet.pet_config.ABILITY_FUNC(pet, pet.player)
    def _proc_friend_ahead_attacked(self):
        friend_ahead_attack: List['PetState'] = []
        if len(self.player.battle_pets) >= 2:
            pet = self.player.battle_pets[1]
            if pet.pet_config.ABILITY_TYPE == AbilityType.FRIEND_AHEAD_ATTACK:
                friend_ahead_attack.append(pet)
        if len(self.challenger.battle_pets) >= 2:
            pet = self.challenger.battle_pets[1]
            if pet.pet_config.ABILITY_TYPE == AbilityType.FRIEND_AHEAD_ATTACK:
                friend_ahead_attack.append(pet)
        for pet in self._priority_sort(friend_ahead_attack):
            pet.pet_config.ABILITY_FUNC(pet, pet.player)
    def _add_to_knockout(self, player_front: 'PetState', challenger_front: 'PetState'):
        if player_front.is_alive() and not challenger_front.is_alive():
            self.knockout = player_front
        elif challenger_front.is_alive() and not player_front.is_alive():
            self.knockout = challenger_front
    def _proc_knockout(self):
        if self.knockout is not None and self.knockout.pet_config.ABILITY_TYPE == AbilityType.KNOCKOUT:
            self.knockout.pet_config.ABILITY_FUNC(self.knockout, self.knockout.player)
class TerminationType(Enum):
    SUCCESS = 1
    OPEN_TIMEOUT = 2
    WRITE_TIMEOUT = 3
    READ_TIMEOUT = 4
    INVALID_MOVE = 5
    CANNOT_PARSE_INPUT = 6
    CUMULATIVE_TIMEOUT = 7
    CANCELLED_MATCH = 8
# class OutputHandler:
#     def __init__(self, state: 'GameState', log: 'GameLog'):
#         self.state = state
#         self.log = log
#     def terminate_success(self, player_ranking: List[int]):
#         self._write_results(TerminationType.SUCCESS, player_ranking = player_ranking)
#         # Write the game log for each player
#         for player in self.state.players:
#             self._write_game_log(player.player_num, self.log.get_game_log(player))
#         # Copy all the players stdout so they can see debug info
#         for player in self.state.players:
#             self._copy_player_stdout(player.player_num)
#         #End the game
#         print("TERMINATE SUCCESS")
#         sys.exit(0)
#     def terminate_cancel(self):
#         self._write_results(TerminationType.CANCELLED_MATCH)
#         print("TERMINATE CANCEL")
#         sys.exit(0) # End the game
#     def terminate_fail(self, termination_type: 'TerminationType', player: 'PlayerState', exception: Optional[Exception] = None, reason: Optional[str] = None):
#         self._write_results(termination_type, faulty_player_num = player.player_num)
#         # Write the game log for the faulty player
#         self._write_game_log(player.player_num, self.log.get_game_log(player))
#         # If we're given an exception or reason, we will populate the stderr with it
#         error: str = None
#         if exception is not None:
#             error = "".join(TracebackException.from_exception(exception).format())
#         elif reason is not None:
#             error = reason
#         # If no error is given, we will just copy stderr from
#         # their submission in case it contains valuable information
#         if error is not None:
#             self._write_player_stderr(player.player_num, error)
#         else:
#             self._copy_player_stderr(player.player_num)
#         self._copy_player_stdout(player.player_num)
#         # End the game
#         print("TERMINATE FAIL")
#         sys.exit(0)
#     def _write_results(self, termination_type: 'TerminationType', faulty_player_num: Optional[int] = None, player_ranking: Optional[List[int]] = None):
#         results: dict = None
#         if termination_type == TerminationType.SUCCESS:
#             results = {
#                 "result_type": termination_type.name,
#                 "ranking": player_ranking
#             }
#         elif termination_type == TerminationType.CANCELLED_MATCH:
#             results = {
#                 "result_type": termination_type.name
#             }
#         else:
#             results = {
#                 "result_type": termination_type.name,
#                 "submission_responsible": faulty_player_num
#             }
#         # TODO add json schema
#         # jsonschema.validate(data, RESULTS_SCHEMA)
#         with open(f"{CORE_DIRECTORY}/output/results.json", 'w') as file:
#             dump(results, file)
#     def _write_game_log(self, player_num: int, game_log: str):
#         with open(f"{CORE_DIRECTORY}/output/game_{player_num}.md", 'w') as file:
#             file.write(game_log)
#     def _write_player_stderr(self, player_num: int, error: str):
#         with open(f"{CORE_DIRECTORY}/output/submission_{player_num}.err", 'w') as file:
#             file.write(error)
#     def _copy_player_stderr(self, player_num: int):
#         submission_path = f"{CORE_DIRECTORY}/submission{player_num}/io/submission.err"
#         output_path = f"{CORE_DIRECTORY}/output/submission_{player_num}.err"
#         try:
#             shutil.copy(submission_path, output_path, follow_symlinks = False)
#         except (FileNotFoundError, IsADirectoryError, FileExistsError):
#             with open(output_path, 'w') as file:
#                 file.write("Nice try. Please don't delete your submission.err file")
#     def _copy_player_stdout(self, player_num: int):
#         submission_path = f"{CORE_DIRECTORY}/submission{player_num}/io/submission.log"
#         output_path = f"{CORE_DIRECTORY}/output/submission_{player_num}.log"
#         try:
#             shutil.copy(submission_path, output_path, follow_symlinks = False)
#         except (FileNotFoundError, IsADirectoryError, FileExistsError):
#             with open(output_path, 'w') as file:
#                 file.write("Nice try. Please don't delete your submission.log file")
class MoveType(Enum):
    BUY_PET = 1
    BUY_FOOD = 2
    UPGRADE_PET_FROM_SHOP = 3
    UPGRADE_PET_FROM_PETS = 4
    SELL_PET = 5
    REROLL = 6
    FREEZE_PET = 7
    FREEZE_FOOD = 8
    UNFREEZE_PET = 9
    UNFREEZE_FOOD = 10
    SWAP_PET = 11
    END_TURN = 12
class PlayerInput:
    def __init__(self, move_type: 'MoveType', input_dict: dict):
        self.move_type = move_type
        self.index_from: int = input_dict["index_from"] if "index_from" in input_dict else None
        self.index_to: int = input_dict["index_to"] if "index_to" in input_dict else None
class InputValidator:
    @staticmethod
    def validate_input(input: 'PlayerInput', player: 'PlayerState', state: 'GameState') -> Tuple[bool, str]:
        return_message = ""
        if input.move_type == MoveType.BUY_PET:
            return_message = InputValidator._validate_buy_pet(input, player)
        elif input.move_type == MoveType.BUY_FOOD:
            return_message = InputValidator._validate_buy_food(input, player)
        elif input.move_type == MoveType.UPGRADE_PET_FROM_PETS:
            return_message = InputValidator._validate_upgrade_pet_from_pet(input, player)
        elif input.move_type == MoveType.UPGRADE_PET_FROM_SHOP:
            return_message = InputValidator._validate_upgrade_pet_from_shop(input, player)
        elif input.move_type == MoveType.SELL_PET:
            return_message = InputValidator._validate_sell_pet(input, player)
        elif input.move_type == MoveType.REROLL:
            return_message = InputValidator._validate_reroll(input, player)
        elif input.move_type == MoveType.FREEZE_PET:
            return_message = InputValidator._validate_freeze_pet(input, player)
        elif input.move_type == MoveType.FREEZE_FOOD:
            return_message = InputValidator._validate_freeze_food(input, player)
        elif input.move_type == MoveType.UNFREEZE_PET:
            return_message = InputValidator._validate_unfreeze_pet(input, player)
        elif input.move_type == MoveType.UNFREEZE_FOOD:
            return_message = InputValidator._validate_unfreeze_food(input, player)
        elif input.move_type == MoveType.SWAP_PET:
            return_message = InputValidator._validate_swap_pets(input, player)
        is_valid = return_message == ""
        if not is_valid:
            return_message = f"Invalid {input.move_type}:\n{return_message}"
        return is_valid, return_message
    @staticmethod
    def _validate_buy_pet(input: 'PlayerInput', player: 'PlayerState') -> str:
        return_message = ""
        return_message += InputValidator._check_shop_pets_index_in_range(player, input.index_from)
        return_message += InputValidator._check_target_pet_index(player, input.index_to, should_be_empty = True)
        return_message += InputValidator._check_sufficient_coins_for_pet(player)
        return return_message
    @staticmethod
    def _validate_buy_food(input: 'PlayerInput', player: 'PlayerState') -> str:
        return_message = ""
        return_message = InputValidator._check_shop_foods_index_in_range(player, input.index_from)
        if return_message != "": return return_message
        food = player.shop_foods[input.index_from]
        return_message += InputValidator._check_food_has_target(player, food, input.index_to)
        return_message += InputValidator._check_sufficient_coins_for_food(player, food)
        return return_message
    @staticmethod
    def _validate_upgrade_pet_from_pet(input: 'PlayerInput', player: 'PlayerState') -> str:
        return_message = ""
        from_pet_message = InputValidator._check_from_pet_index(player, input.index_from, should_be_empty = False)
        target_pet_message = InputValidator._check_target_pet_index(player, input.index_to, should_be_empty = False)
        return_message += from_pet_message
        return_message += target_pet_message
        if from_pet_message == "" and target_pet_message == "":
            return_message += InputValidator._check_pets_for_level_up(player.pets[input.index_from], player.pets[input.index_to])
        if input.index_from == input.index_to:
            return_message += "You cannot upgrade a pet using itself"
        return return_message
    @staticmethod
    def _validate_upgrade_pet_from_shop(input: 'PlayerInput', player: 'PlayerState') -> str:
        return_message = ""
        shop_pet_message = InputValidator._check_shop_pets_index_in_range(player, input.index_from)
        target_pet_message = InputValidator._check_target_pet_index(player, input.index_to, should_be_empty = False)
        return_message += shop_pet_message
        return_message += target_pet_message
        if shop_pet_message == "" and target_pet_message == "":
            return_message += InputValidator._check_pets_for_level_up(player.shop_pets[input.index_from], player.pets[input.index_to])
        return_message += InputValidator._check_sufficient_coins_for_pet(player)
        return return_message
    @staticmethod
    def _validate_sell_pet(input: 'PlayerInput', player: 'PlayerState') -> str:
        return InputValidator._check_from_pet_index(player, input.index_from, should_be_empty = False)
    @staticmethod
    def _validate_reroll(input: 'PlayerInput', player: 'PlayerState') -> str:
        if player.coins < REROLL_COST:
            return f"Not enough currency to reroll. You need {REROLL_COST} but only have {player.coins} available\n"
        else:
            return ""
    @staticmethod
    def _validate_freeze_pet(input: 'PlayerInput', player: 'PlayerState') -> str:
        return_message = InputValidator._check_shop_pets_index_in_range(player, input.index_from)
        if return_message != "": return return_message
        if player.shop_pets[input.index_from].is_frozen:
            return f"Shop Pet at index {input.index_from} is already frozen\n"
        else:
            return ""
    @staticmethod
    def _validate_freeze_food(input: 'PlayerInput', player: 'PlayerState') -> str:
        return_message = InputValidator._check_shop_foods_index_in_range(player, input.index_from)
        if return_message != "": return return_message
        if player.shop_foods[input.index_from].is_frozen:
            return f"Shop Food at index {input.index_from} is already frozen\n"
        else:
            return ""
    @staticmethod
    def _validate_unfreeze_pet(input: 'PlayerInput', player: 'PlayerState') -> str:
        return_message = InputValidator._check_shop_pets_index_in_range(player, input.index_from)
        if return_message != "": return return_message
        if not player.shop_pets[input.index_from].is_frozen:
            return f"Shop Pet at index {input.index_from} is already unfrozen\n"
        else:
            return ""
    @staticmethod
    def _validate_unfreeze_food(input: 'PlayerInput', player: 'PlayerState') -> str:
        return_message = InputValidator._check_shop_foods_index_in_range(player, input.index_from)
        if return_message != "": return return_message
        if not player.shop_foods[input.index_from].is_frozen:
            return f"Shop Food at index {input.index_from} is already unfrozen\n"
        else:
            return ""
    @staticmethod
    def _validate_swap_pets(input: 'PlayerInput', player: 'PlayerState') -> str:
        return_message = ""
        if input.index_from not in range(0, PET_POSITIONS):
            return_message += f"Pet A position {input.index_from} is invalid. The index {input.index_from} is not in the range [0, {PET_POSITIONS - 1}]\n"
        if input.index_to not in range(0, PET_POSITIONS):
            return_message += f"Pet B position {input.index_to} is invalid. The index {input.index_to} is not in the range [0, {PET_POSITIONS - 1}]\n"
        return return_message
    @staticmethod
    def _check_shop_pets_index_in_range(player: 'PlayerState', index: int) -> str:
        if index not in range(0, len(player.shop_pets)):
            return f"Shop Pet is invalid. The index {index} is not in the range [0, {len(player.shop_pets) - 1}]\n"
        else:
            return ""
    @staticmethod
    def _check_shop_foods_index_in_range(player: 'PlayerState', index: int) -> str:
        if index not in range(0, len(player.shop_foods)):
            return f"Shop Food is invalid. The index {index} is not in the range [0, {len(player.shop_foods) - 1}]\n"
        else:
            return ""
    @staticmethod
    def _check_target_pet_index(player: 'PlayerState', index: int, should_be_empty: bool) -> str:
        if index not in range(0, PET_POSITIONS):
            return f"Target pet position {index} is not in the range [0, {PET_POSITIONS - 1}]\n"
        elif player.pets[index] is not None and should_be_empty:
            return f"Target pet position {index} is already occupied\n"
        elif player.pets[index] is None and not should_be_empty:
            return f"Target pet position {index} is not occupied\n"
        else:
            return ""
    @staticmethod
    def _check_from_pet_index(player: 'PlayerState', index: int, should_be_empty: bool) -> str:
        if index not in range(0, PET_POSITIONS):
            return f"From pet position {index} is not in the range [0, {PET_POSITIONS - 1}]\n"
        elif player.pets[index] is not None and should_be_empty:
            return f"From pet position {index} is already occupied\n"
        elif player.pets[index] is None and not should_be_empty:
            return f"From pet position {index} is not occupied\n"
        else:
            return ""
    @staticmethod
    def _check_food_has_target(player: 'PlayerState', food: 'FoodState', index: int) -> str:
        if food.food_config.IS_TARGETED:
            return InputValidator._check_target_pet_index(player, index, should_be_empty = False)
        else:
            return ""
    @staticmethod
    def _check_sufficient_coins_for_pet(player: 'PlayerState') -> str:
        if player.coins < PET_BUY_COST:
            return f"Not enough currency to buy pet. You need {PET_BUY_COST} but only have {player.coins} available\n"
        else:
            return ""
    @staticmethod
    def _check_sufficient_coins_for_food(player: 'PlayerState', food: 'FoodState') -> str:
        if player.coins < food.cost:
            return f"Not enough currency to buy food. You need {food.cost} but only have {player.coins} available\n"
        else:
            return ""
    @staticmethod
    def _check_pets_for_level_up(from_pet: 'PetState', to_pet: 'PetState'):
        return_message = ""
        if from_pet.get_level() == 3 or to_pet.get_level() == 3:
            return_message +=  "Cannot use a level 3 pet for leveling up\n"
        if from_pet.pet_config.PET_NAME != to_pet.pet_config.PET_NAME:
            return_message += "You must use two pets of the same type to level up\n"
        return return_message
# class InputHelper:
#     def __init__(self, state: 'GameState', output_handler: 'OutputHandler'):
#         self.state = state
#         self.output_handler = output_handler
#         curr_player_num = 0
#         def open_pipe_timeout_handler(a, b):
#             self.output_handler.terminate_fail(TerminationType.OPEN_TIMEOUT, self.state.players[curr_player_num])
#         signal(SIGALRM, open_pipe_timeout_handler)
#         self.from_engine_pipes = []
#         self.to_engine_pipes = []
#         for curr_player_num in range(NUM_PLAYERS):
#             alarm(OPEN_PIPE_TIMEOUT_SECONDS) # Enable timer
#             start = time()
#             self.from_engine_pipes.append(open(self._get_pipe_path(curr_player_num, from_engine = True), 'w'))
#             self.to_engine_pipes.append(open(self._get_pipe_path(curr_player_num, from_engine = False), 'r'))
#             end = time()
#             alarm(0) # Disable timer
#             self._add_cumulative_time(self.state.players[curr_player_num], start, end)
#     def get_player_input(self, player: 'PlayerState', remaining_moves: int) -> 'PlayerInput':
#         self._send_view_to_player(player, self.state.get_view(player, remaining_moves))
#         input = self._receive_input_from_player(player)
#         valid, reason = InputValidator.validate_input(input, player, self.state)
#         if not valid:
#             self.output_handler.terminate_fail(TerminationType.INVALID_MOVE, player, reason = reason)
#         return input
#     def _get_pipe_path(self, player_num, from_engine: bool) -> str:
#         ending = "from_engine.pipe" if from_engine else "to_engine.pipe"
#         return f"{CORE_DIRECTORY}/submission{player_num}/io/{ending}"
#     def _send_view_to_player(self, player: 'PlayerState', view: dict):
#         def write_pipe_timeout_handler(a, b):
#             self.output_handler.terminate_fail(TerminationType.WRITE_TIMEOUT, player)
#         signal(SIGALRM, write_pipe_timeout_handler)
#         json = dumps(view)
#         json += ";"
#         alarm(WRITE_PIPE_TIMEOUT_SECONDS) # Enable timer
#         start = time()
#         try:
#             self.from_engine_pipes[player.player_num].write(json)
#             self.from_engine_pipes[player.player_num].flush()
#         except BrokenPipeError:
#             self.output_handler.terminate_fail(TerminationType.WRITE_TIMEOUT, player)
#         end = time()
#         alarm(0) # Disable timer
#         self._add_cumulative_time(player, start, end)
#     def _receive_input_from_player(self, player: 'PlayerState') -> 'PlayerInput':
#         def read_pipe_timeout_handler(a, b):
#             self.output_handler.terminate_fail(TerminationType.READ_TIMEOUT, player)
#         signal(SIGALRM, read_pipe_timeout_handler)
#         json = ''
#         alarm(READ_PIPE_TIMEOUT_SECONDS) # Enable timer
#         start = time()
#         try:
#             while not json or json[-1] != ';':
#                 json += self.to_engine_pipes[player.player_num].read(1)
#         except BrokenPipeError:
#             self.output_handler.terminate_fail(TerminationType.READ_TIMEOUT, player)
#         end = time()
#         alarm(0) # Disable timer
#         self._add_cumulative_time(player, start, end)
#         # Remove ";"
#         json = json[:-1]
#         try:
#             input_dict = loads(json)
#             move_type = MoveType[input_dict["move_type"]]
#             return PlayerInput(move_type, input_dict)
#         except Exception as exception:
#             self.output_handler.terminate_fail(TerminationType.CANNOT_PARSE_INPUT, player, exception = exception)
#     def _add_cumulative_time(self, player: 'PlayerState', start: float, end: float):
#         player.cumulative_time += (end - start)
#         if player.cumulative_time > CUMULATIVE_MAX_TIME:
#             self.output_handler.terminate_fail(TerminationType.CUMULATIVE_TIMEOUT, player, reason=f"Throughout the game, your submission took longer than {CUMULATIVE_MAX_TIME}s to play moves")
class BuyStageHelper:
    def __init__(self, state: 'GameState', log: 'GameLog', output_handler: 'OutputHandler'):
        self.state = state
        self.log = log
        self.output_handler = output_handler
    #     self.input_helper = InputHelper(state, output_handler)
    # def run(self, player: 'PlayerState'):
    #     for moves in range(MAX_MOVES_PER_ROUND):
    #         input = self.input_helper.get_player_input(player, MAX_MOVES_PER_ROUND - moves)
    #         if input.move_type == MoveType.BUY_PET:
    #             self._buy_pet(player, input)
    #         elif input.move_type == MoveType.BUY_FOOD:
    #             self._buy_food(player, input)
    #         elif input.move_type == MoveType.UPGRADE_PET_FROM_PETS:
    #             self._upgrade_pet_from_pets(player, input)
    #         elif input.move_type == MoveType.UPGRADE_PET_FROM_SHOP:
    #             self._upgrade_pet_from_shop(player, input)
    #         elif input.move_type == MoveType.SELL_PET:
    #             self._sell_pet(player, input)
    #         elif input.move_type == MoveType.REROLL:
    #             self._reroll(player, input)
    #         elif input.move_type == MoveType.FREEZE_PET:
    #             self._freeze_pet(player, input)
    #         elif input.move_type == MoveType.FREEZE_FOOD:
    #             self._freeze_food(player, input)
    #         elif input.move_type == MoveType.UNFREEZE_PET:
    #             self._unfreeze_pet(player, input)
    #         elif input.move_type == MoveType.UNFREEZE_FOOD:
    #             self._unfreeze_food(player, input)
    #         elif input.move_type == MoveType.SWAP_PET:
    #             self._swap_pet(player, input)
    #         elif input.move_type == MoveType.END_TURN:
    #             self.log.write_buy_stage_log(player, "End turn")
    #             return
    #         else:
    #             raise Exception(f'Invalid move type: {input.move_type}')
    def _buy_pet(self, player: 'PlayerState', input: 'PlayerInput'):
        new_pet = player.shop_pets[input.index_from]
        player.shop_pets.remove(new_pet)
        player.coins -= PET_BUY_COST
        player.pets[input.index_to] = new_pet
        new_pet.proc_on_demand_ability(AbilityType.BUY)
        player.friend_summoned(new_pet)
        log = f"Bought {new_pet} for position {input.index_to + 1}; {player.coins} remaining coins"
        self.log.write_buy_stage_log(player, log)
    def _buy_food(self, player: 'PlayerState', input: 'PlayerInput'):
        food = player.shop_foods[input.index_from]
        player.shop_foods.remove(food)
        player.coins -= food.cost
        log = f"Bought {food}"
        pet: Optional['PetState'] = None
        if food.food_config.IS_TARGETED:
            pet = player.pets[input.index_to]
            log += f" for {pet}"
        log += f"; {player.coins} remaining coins"
        # For carried food, the effects are hard-coded
        if food.food_config.IS_CARRIED:
            assert pet is not None
            pet.carried_food = food.food_config
        else:
            food.food_config.EFFECT_FUNC(pet, player, self.state)
        self.log.write_buy_stage_log(player, log)
    def _upgrade_pet_from_pets(self, player: 'PlayerState', input: 'PlayerInput'):
        from_pet = player.pets[input.index_from]
        player.pets[input.index_from] = None
        to_pet = player.pets[input.index_to]
        to_pet.level_up(from_pet)
        log = f"Leveled up {to_pet} using {from_pet}"
        self.log.write_buy_stage_log(player, log)
    def _upgrade_pet_from_shop(self, player: 'PlayerState', input: 'PlayerInput'):
        shop_pet = player.shop_pets[input.index_from]
        player.shop_pets.remove(shop_pet)
        player.coins -= PET_BUY_COST
        pet = player.pets[input.index_to]
        pet.level_up(shop_pet)
        pet.proc_on_demand_ability(AbilityType.BUY)
        player.friend_summoned(pet)
        log = f"Leveled up {pet} by buying {shop_pet}; {player.coins} remaining coins"
        self.log.write_buy_stage_log(player, log)
    def _sell_pet(self, player: 'PlayerState', input: 'PlayerInput'):
        pet = player.pets[input.index_from]
        player.pets[input.index_from] = None
        pet.proc_on_demand_ability(AbilityType.SELL)
        player.coins += pet.get_level()
        log = f"Sold {pet}; Now have {player.coins} coins"
        self.log.write_buy_stage_log(player, log)
    def _reroll(self, player: 'PlayerState', input: 'PlayerInput'):
        player.reset_shop_options()
        player.coins -= REROLL_COST
        log = f"Rerolled shop; {player.coins} remaining coins"
        self.log.write_buy_stage_log(player, log)
    def _freeze_pet(self, player: 'PlayerState', input: 'PlayerInput'):
        pet = player.shop_pets[input.index_from]
        pet.is_frozen = True
        log = f"Froze {pet}"
        self.log.write_buy_stage_log(player, log)
    def _freeze_food(self, player: 'PlayerState', input: 'PlayerInput'):
        food = player.shop_foods[input.index_from]
        food.is_frozen = True
        log = f"Froze {food}"
        self.log.write_buy_stage_log(player, log)
    def _unfreeze_pet(self, player: 'PlayerState', input: 'PlayerInput'):
        pet = player.shop_pets[input.index_from]
        pet.is_frozen = False
        log = f"Unfroze {pet}"
        self.log.write_buy_stage_log(player, log)
    def _unfreeze_food(self, player: 'PlayerState', input: 'PlayerInput'):
        food = player.shop_foods[input.index_from]
        food.is_frozen = False
        log = f"Unfroze {food}"
        self.log.write_buy_stage_log(player, log)
    def _swap_pet(self, player: 'PlayerState', input: 'PlayerInput'):
        pet_a = player.pets[input.index_from]
        pet_b = player.pets[input.index_to]
        player.pets[input.index_from] = pet_b
        player.pets[input.index_to] = pet_a
        log = ""
        if pet_a is not None and pet_b is not None:
            log = f"Swapped {pet_a} @ {input.index_from + 1} and {pet_b} @ {input.index_to + 1}"
        elif pet_a is not None:
            log = f"Moved {pet_a} to empty position {input.index_to + 1}"
        elif pet_b is not None:
            log = f"Moved {pet_b} to empty position {input.index_from + 1}"
        else:
            log = f"Swapped two empty positions {input.index_to + 1} and {input.index_from + 1}"
        self.log.write_buy_stage_log(player, log)
class FoodState:
    def __init__(self, food_config: 'FoodConfig', state: 'GameState'):
        self.id = state.get_id()
        self.food_config = food_config
        self.cost = food_config.BUY_COST
        self.is_frozen = False
    def get_view_for_shop(self) -> dict:
        return {
            "id": self.id,
            "type": self.food_config.FOOD_NAME,
            "is_frozen": self.is_frozen,
            "cost": self.cost
        }
    def __repr__(self) -> str:
        return f"{self.food_config.FOOD_NAME}:{self.id}"
class GameState:
    def __init__(self):
        self.round = -1
        self.players = [PlayerState(i, self) for i in range(NUM_PLAYERS)]
        self.dead_players: List['PlayerState'] = []
        self._next_id = 0
    def start_new_round(self):
        self.round += 1
        for player in self.players:
            player.start_new_round()
    def start_battle_stage(self):
        for player in self.get_alive_players():
            player.start_battle_stage()
    def end_round(self):
        for player in self.players:
            if not player.is_alive() and player not in self.dead_players:
                self.dead_players.append(player)
    def get_alive_players(self) -> List['PlayerState']:
        return [player for player in self.players if player.is_alive()]
    def is_game_over(self) -> bool:
        alive_players = self.get_alive_players()
        num_alive = len(alive_players)
        return num_alive == 1
    def get_player_ranking(self) -> List[int]:
        player_ranking = []
        # Add the winning player
        player_ranking.append(self.get_alive_players()[0].player_num)
        # Add the dead players
        # Latest death is at the end of the list so we traverse in reverse
        for player in reversed(self.dead_players):
            player_ranking.append(player.player_num)
        return player_ranking
    def get_view(self, player: 'PlayerState', remaining_moves: int) -> dict:
        next_opponent = player.challenger
        other_players = [alive_player for alive_player in self.get_alive_players() if alive_player != player]
        return {
            "round": self.round + 1,
            "remaining_moves": remaining_moves,
            "player_info": player.get_view_for_self(),
            "next_opponent_index": other_players.index(next_opponent),
            "other_players_info": [other_player.get_view_for_others() for other_player in other_players]
        }
    def get_id(self) -> int:
        id = self._next_id
        self._next_id += 1
        return id
class PetState:
    def __init__(self, health: int, attack: int, pet_config: 'PetConfig', player: 'PlayerState', state: 'GameState'):
        self.player = player
        self.state = state
        self.id = self.state.get_id()
        self.pet_config = pet_config
        self._perm_health = health
        self._perm_attack = attack
        self._health = health
        self._attack = attack
        self.prev_health = health
        self.prev_attack = attack
        self.carried_food: Optional['FoodConfig'] = None
        self.prev_carried_food: Optional['FoodConfig'] = None
        self.sub_level = 0
        self.prev_level = 1
        self.is_frozen = False
    def start_new_round(self):
        self.prev_health = self._perm_health
        self.prev_attack = self._perm_attack
        self.prev_carried_food = self.carried_food
        self.prev_level = self.get_level()
        self._health = self._perm_health
        self._attack = self._perm_attack
        self.proc_on_demand_ability(AbilityType.BUY_ROUND_START)
    def get_level(self):
        if self.sub_level == LEVEL_3_CUTOFF:
            return 3
        elif self.sub_level >= LEVEL_2_CUTOFF:
            return 2
        else:
            return 1
    def get_sub_level_progress(self):
        level = self.get_level()
        if level == 3:
            return 0
        elif level == 2:
            return self.sub_level - LEVEL_2_CUTOFF
        else:
            return self.sub_level
    def level_up(self, other_pet: 'PetState'):
        old_level = self.get_level()
        self.sub_level += other_pet.sub_level + 1
        self.sub_level = min(self.sub_level, LEVEL_3_CUTOFF)
        new_level = self.get_level()
        temp_health = self._health - self._perm_health
        temp_attack = self._attack - self._perm_attack
        new_health = max(self._perm_health, other_pet._perm_health) + 1
        new_attack = max(self._perm_attack, other_pet._perm_attack) + 1
        self._set_perm_health(new_health)
        self._set_perm_attack(new_attack)
        self._set_health(new_health + temp_health)
        self._set_attack(new_attack + temp_attack)
        if old_level < new_level:
            self.player.add_level_up_shop_pet()
            self.proc_on_demand_ability(AbilityType.LEVEL_UP)
    def damage_enemy_with_attack(self, enemy_pet: 'PetState'):
        enemy_pet._take_damage(self._attack + self.get_bonus_attack())
    def damage_enemy_with_ability(self, attack, enemy_pet: 'PetState'):
        enemy_pet._take_damage(attack)
    def proc_on_demand_ability(self, ability_type: AbilityType):
        if self.pet_config.ABILITY_TYPE == ability_type:
            self.pet_config.ABILITY_FUNC(self, self.player)
    def perm_increase_health(self, amount: int):
        self.change_health(amount)
        self._set_perm_health(self._perm_health + amount)
    def perm_increase_attack(self, amount: int):
        self.change_attack(amount)
        self._set_perm_attack(self._perm_attack + amount)
    def change_health(self, amount: int):
        self._set_health(self._health + amount)
    def change_attack(self, amount: int):
        self._set_attack(self._attack + amount)
    def get_bonus_attack(self) -> int:
        if self.carried_food == FOOD_CONFIG[FoodType.MEAT_BONE]:
            return 3
        else:
            return 0
    def get_health(self) -> int:
        return self._health
    def get_attack(self) -> int:
        return self._attack
    def get_perm_health(self) -> int:
        return self._perm_health
    def get_perm_attack(self) -> int:
        return self._perm_attack
    def is_alive(self) -> bool:
        return self._health > 0
    def get_view_for_self(self) -> dict:
        return {
            "id": self.id,
            "type": self.pet_config.PET_NAME,
            "health": self._health,
            "attack": self._attack,
            "level": self.get_level(),
            "sub_level": self.get_sub_level_progress(),
            "carried_food": self.carried_food.FOOD_NAME if self.carried_food is not None else None
        }
    def get_view_for_shop(self) -> dict:
        return {
            "id": self.id,
            "type": self.pet_config.PET_NAME,
            "health": self._health,
            "attack": self._attack,
            "is_frozen": self.is_frozen,
            "cost": PET_BUY_COST
        }
    def get_view_for_others(self) -> dict:
        return {
            "id": self.id,
            "type": self.pet_config.PET_NAME,
            "health": self.prev_health,
            "attack": self.prev_attack,
            "level": self.prev_level,
            "carried_food": self.prev_carried_food.FOOD_NAME if self.prev_carried_food is not None else None
        }
    def on_death(self):
        if self.pet_config.ABILITY_TYPE == AbilityType.FAINTED:
            self.player.battle.add_hurt_or_fainted_or_bee(self)
        if self.carried_food == FOOD_CONFIG[FoodType.HONEY]:
            self.player.battle.add_hurt_or_fainted_or_bee(self)
    def _set_health(self, health: int):
        self._health = min(max(0, health), 50)
    def _set_attack(self, attack: int):
        self._attack = min(max(0, attack), 50)
    def _set_perm_health(self, perm_health: int):
        self._perm_health = min(max(0, perm_health), 50)
    def _set_perm_attack(self, perm_attack: int):
        self._perm_attack = min(max(0, perm_attack), 50)
    def _take_damage(self, amount: int):
        if not self.is_alive(): return
        if self.carried_food == FOOD_CONFIG[FoodType.GARLIC]:
            amount = max(amount - 2, 1)
        self.change_health(-amount)
        if self.pet_config.ABILITY_TYPE == AbilityType.HURT:
            self.player.battle.add_hurt_or_fainted_or_bee(self)
        if not self.is_alive():
            self.on_death()
    def __repr__(self) -> str:
        return f"{self.pet_config.PET_NAME}:{self.id}"
class PlayerState:
    def __init__(self, player_num: int, state: 'GameState'):
        self.player_num = player_num
        self.state = state
        self.cumulative_time: float = 0
        self.health = STARTING_HEALTH
        self.pets: List[Optional['PetState']] = [None] * PET_POSITIONS
        self.shop_pets: List['PetState'] = []
        self.shop_foods: List['FoodState'] = []
        self.shop_perm_health_bonus = 0
        self.shop_perm_attack_bonus = 0
        # Represents who you are currently battling. This can change to multiple different
        # players during a single battle stage
        self.opponent: Optional['PlayerState'] = None
        # Represents a copy of your pets for the purpose of running a battle
        self.battle_pets: List['PetState'] = []
        # Represents who will be challenging you during the battle stage
        # Will only be a single player for an entire battle stage
        self.challenger: Optional['PlayerState'] = None
        self.battle_order = [i for i in range(NUM_PLAYERS) if i != player_num]
        shuffle(self.battle_order)
        self.next_battle_index = 0
        # Represents the current battle the player is in
        self.battle: Optional['Battle'] = None
        # Contains a reference to the newest summoned pet for use in
        # FRIEND_SUMMON abilities
        self.new_summoned_pet: Optional['PetState'] = None
        # Contains a reference to the pet that just ate food
        # for use in FRIEND_ATE_FOOD abilities
        self.pet_that_ate_food: Optional['PetState'] = None
    def start_new_round(self):
        self.prev_health = self.health
        self.prev_pets = self._get_pets_copy()
        self.coins = STARTING_COINS
        self.reset_shop_options()
        self._update_challenger()
        for pet in self.pets:
            if pet is not None:
                pet.start_new_round()
    def start_battle_stage(self):
        for pet in self.pets:
            if pet is not None:
                pet.proc_on_demand_ability(AbilityType.BUY_ROUND_END)
    # We copy the battle pets so we can make irreversible changes
    # during a battle
    def start_battle(self, opponent: 'PlayerState'):
        self.opponent = opponent
        self.battle_pets = self._get_pets_copy()
    def reset_shop_options(self):
        round_config = RoundConfig.get_round_config(self.state.round)
        self.shop_pets = [pet for pet in self.shop_pets if pet.is_frozen]
        pets_to_add = round_config.NUM_SHOP_PETS - len(self.shop_pets)
        for _ in range(pets_to_add):
            shop_pet = self._create_shop_pet(self._get_random_pet_type(round_config.MAX_SHOP_TIER))
            self.shop_pets.append(shop_pet)
        self.shop_foods = [food for food in self.shop_foods if food.is_frozen]
        foods_to_add = round_config.NUM_SHOP_FOODS - len(self.shop_foods)
        for _ in range(foods_to_add):
            food_config = FOOD_CONFIG[self._get_random_food_type(round_config.MAX_SHOP_TIER)]
            self.shop_foods.append(FoodState(food_config, self.state))
    def add_level_up_shop_pet(self):
        round_config = RoundConfig.get_round_config(self.state.round)
        tier = min(round_config.MAX_SHOP_TIER + 1, MAX_SHOP_TIER)
        pet_type = choice(TIER_PETS[tier - 1])
        shop_pet = self._create_shop_pet(pet_type)
        self.shop_pets.append(shop_pet)
    def summon_bee(self, original_pet: 'PetState'):
        bee_config = PET_CONFIG[PetType.BEE]
        bee = PetState(bee_config.BASE_HEALTH, bee_config.BASE_ATTACK, bee_config, self, self.state)
        self.summon_pets(original_pet, [bee])
    def create_pet_to_summon(self, pet_type: 'PetType', health: int, attack: int):
        pet_config = PET_CONFIG[pet_type]
        pet = PetState(health, attack, pet_config, self, self.state)
        return pet
    def summon_pets(self, original_pet: 'PetState', pets_to_summon: List['PetState']):
        # We insert the pets at where the dying pet is
        insert_at_index = self.battle_pets.index(original_pet)
        # How many pets are we accepting
        num_alive = len([pet for pet in self.battle_pets if pet.is_alive()])
        num_summons = min(PET_POSITIONS - num_alive, len(pets_to_summon))
        # List of pets we are summoning
        pets_to_summon = pets_to_summon[:num_summons]
        for pet in pets_to_summon:
            self.battle_pets.insert(insert_at_index, pet)
            self.friend_summoned(pet)
    def friend_summoned(self, new_pet: 'PetState'):
        self.new_summoned_pet = new_pet
        for pet in self.battle_pets:
            if pet != new_pet and pet.is_alive():
                pet.proc_on_demand_ability(AbilityType.FRIEND_SUMMONED)
        # Clear the reference now its not needed
        self.new_summoned_pet = None
    def friend_ate_food(self, fat_pet: 'PetState'):
        self.pet_that_ate_food = fat_pet
        for pet in self.pets:
            if pet is not None:
                pet.proc_on_demand_ability(AbilityType.FRIEND_ATE_FOOD)
        # Clear the reference now its not needed
        self.pet_that_ate_food = None
    def is_alive(self) -> bool:
        return self.health > 0
    def get_view_for_self(self) -> dict:
        return {
            "health": self.health,
            "coins": self.coins,
            "pets": [pet.get_view_for_self() if pet is not None else None for pet in self.pets],
            "shop_pets": [pet.get_view_for_shop() for pet in self.shop_pets],
            "shop_foods": [food.get_view_for_shop() for food in self.shop_foods]
        }
    def get_view_for_others(self) -> dict:
        return {
            "health": self.prev_health,
            "pets": [pet.get_view_for_others() if pet is not None else None for pet in self.prev_pets]
        }
    # Round robin through battle order until the next alive player is found
    def _update_challenger(self):
        i = self.next_battle_index
        while True:
            challenger = self.state.players[self.battle_order[i]]
            i = (i + 1) % (NUM_PLAYERS - 1)
            if challenger.is_alive():
                self.next_battle_index = i
                self.challenger = challenger
                return
    def _create_shop_pet(self, pet_type: 'PetType') -> 'PetState':
        pet_config = PET_CONFIG[pet_type]
        health = pet_config.BASE_HEALTH + self.shop_perm_health_bonus
        attack = pet_config.BASE_ATTACK + self.shop_perm_attack_bonus
        return PetState(health, attack, pet_config, self, self.state)
    def _get_random_pet_type(self, max_shop_tier: int) -> 'PetType':
        return self._get_random_from_config_tiers(TIER_PETS, max_shop_tier)
    def _get_random_food_type(self, max_shop_tier: int) -> 'FoodType':
        return self._get_random_from_config_tiers(TIER_FOOD, max_shop_tier)
    # Simple probability. Every pet/food has an equal chance among the currently
    # allowed tiers
    def _get_random_from_config_tiers(self, config_tiers, max_shop_tier: int):
        total_num = 0
        for tier in range(max_shop_tier):
            total_num += len(config_tiers[tier])
        global_index = randint(0, total_num - 1)
        for tier in range(max_shop_tier):
            if global_index < len(config_tiers[tier]):
                return config_tiers[tier][global_index]
            else:
                global_index -= len(config_tiers[tier])
    def _get_pets_copy(self) -> List['PetState']:
        return [copy(pet) if pet is not None else None for pet in self.pets]
    def __repr__(self) -> str:
        return f"Player {self.player_num + 1}"
# class GameEngine:
#     def __init__(self):
#         self.state = GameState()
#         self.log = GameLog(self.state)
#         self.output_handler = OutputHandler(self.state, self.log)
#         self.buy_stage_helper = BuyStageHelper(self.state, self.log, self.output_handler)
#     def run(self):
#         while not self.state.is_game_over():
#             if self.state.round >= MAX_ROUNDS or len(self.state.get_alive_players()) == 0:
#                 self.output_handler.terminate_cancel()
#             self.state.start_new_round()
#             self.log.write_start_state_logs()
#             players = self.state.get_alive_players()
#             # self.log.init_buy_stage_log()
#             # for player in players:
#             #     self.buy_stage_helper.run(player)
#             self.state.start_battle_stage()
#             self.log.init_battle_stage_log()
#             for player in players:
#                 battle = Battle(player, player.challenger, self.state, self.log)
#                 player.battle = battle
#                 player.challenger.battle = battle
#                 battle.run()
#             self.state.end_round()
#         self.output_handler.terminate_success(self.state.get_player_ranking())
















def powerset(iterable):
    "powerset([1,2,3]) --> () (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)"
    s = list(iterable)
    return chain.from_iterable(combinations(s, r) for r in range(len(s)+1))

def getSublevel(pet):
    if isinstance(pet, PlayerPetInfo):
        return pet.sub_level + LEVEL_2_CUTOFF * (pet.level == 2) + LEVEL_3_CUTOFF * (pet.level == 3)
    else:
        return 0
PlayerPetInfo.__repr__ = PlayerPetInfo.__str__ = ShopPetInfo.__repr__ = ShopPetInfo.__str__ = lambda self: f"<{str(self.type)[8:]}~{self.id} L={getSublevel(self)} H={self.health} A={self.attack}>"
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

def calc_sublevel(pets: List[PlayerPetInfo]):
    return sum(getSublevel(pet) for pet in pets) + len(pets) - 1

def getOutcome(pets: List[Optional[PlayerPetInfo]], opponent_pets: List[Optional[PlayerPetInfo]]) -> int:
    state = GameState()
    
    ans = 0
    def write_battle_log(x, y, battle_lost: Optional[bool], k):
        nonlocal ans
        if battle_lost == True:
            # player B won
            ans = -1
        elif battle_lost is None:
            ans = 0
        else:
            # player A won
            ans = +1
    log = GameLog(state)
    log.write_battle_stage_log = write_battle_log
    
    
    player_a = PlayerState(0, state)
    player_a.pets = [PetState(pet.health, pet.attack, PET_CONFIG[pet.type], player_a, state) for pet in pets if pet]
    player_b = PlayerState(1, state)
    player_b.pets = [PetState(pet.health, pet.attack, PET_CONFIG[pet.type], player_b, state) for pet in opponent_pets if pet]
    
    battle = Battle(player_a, player_b, state, log)
    player_a.battle = battle
    player_b.battle = battle
    battle.run()
    return ans

# 6 calls to getOutcome
def permMetric(perm: List[int], currBest: int):
    # print(perm)
    pets = [G.player_info.pets[i] for i in perm]
    total = 100 * getOutcome(pets, G.next_opponent_info.pets)
    if total + 20 * 1 <= currBest: return total
    
    # for player in G.other_players_info:
    #     total += 10 * getOutcome(pets, player.pets)
    for i in range(20):
        opp = deepcopy(G.next_opponent_info.pets)
        i = randint(0, 4)
        opp[i] = OtherPlayerPetInfo({
            "id": 696969,
            "type": choice(list(PetType.__members__)[:-3]),
            "health": randint(1, 5),
            "attack": randint(1, 4),
            "level": randint(1, 2),
            "sub_level": 0,
            "carried_food": None
        })
        total += 1 * getOutcome(pets, opp)
        if total + (19 - i) * 1 <= currBest: return total

    return total

# stage is `() -> bool`, which returns true immediately when it performs a move

def get_perm(perm):
    perm = list(perm)
    
    actions = []
    for i in range(5):
        if perm[i] != i:
            j = perm.index(i)
            actions.append((i, j))
            perm[i], perm[j] = perm[j], perm[i]
    
    for action in actions:
        bot_battle.swap_pets(*action)
        globals()["G"] = bot_battle.get_game_info()
    return len(actions) > 0

def STAGE_perm():
    # try all permutations, chose best one
    best = -696969
    for perm in permutations(range(5)):
        outcome = permMetric(perm, best)
        if outcome > best:
            best = outcome
            bestPerm = perm
    assert best != -696969

    print("WINNING PERM IS")
    print([G.player_info.pets[i] for i in bestPerm])
    print(best)
    return get_perm(bestPerm)

def STAGE_buy_insert(wanted_pet: ShopPetInfo):
    if None in G.player_info.pets:
        i = G.player_info.pets.index(None)
        print("INSERT", wanted_pet.type, i)
        bot_battle.buy_pet(getPet(wanted_pet), i)
        globals()["G"] = bot_battle.get_game_info()
        return True
    return False

# def STAGE_buy_merge(wanted_type: PetType, wanted_pet: Optional[ShopPetInfo]):
#     pets = []
#     for pet in G.player_info.pets:
#         if pet and pet.type == wanted_type:
#             pets.append(pet)
#     if len(pets) + (wanted_pet is not None) >= 2 and calc_sublevel(pets) + (wanted_pet is not None) in [2, 5]:
#         # merge pet
#         if wanted_pet:
#             bot_battle.level_pet_from_shop(getPet(wanted_pet), getPet(pets[0]))
#             globals()["G"] = bot_battle.get_game_info()
#         for pet in pets[1:]:
#             if getPet(pets[0]).level == 3:
#                 break
#             bot_battle.level_pet_from_pets(getPet(pet), getPet(pets[0]))
#             globals()["G"] = bot_battle.get_game_info()
#         return True
#     return False

def STAGE_buy_merge(wanted_type: PetType, wanted_pet: Optional[ShopPetInfo]):
    assert not wanted_pet or wanted_type == wanted_pet.type
    pets = sorted(collectPets(wanted_type), key=lambda pet: getSublevel(pet), reverse=True)
    if len(pets) >= 1 and wanted_pet:
        print("MERGE", wanted_type)
        # merge shop pet into pet with greatest sublevel
        bot_battle.level_pet_from_shop(getPet(wanted_pet), getPet(pets[0]))
        globals()["G"] = bot_battle.get_game_info()
        return True
    elif len(pets) >= 2:
        print("MERGE", wanted_type)
        # merge the 2 pets with greatest sublevel
        bot_battle.level_pet_from_pets(getPet(pets[0]), getPet(pets[1]))
        globals()["G"] = bot_battle.get_game_info()
        return True
    else:
        return False

def STAGE_buy_merge_any():
    for pet in G.player_info.pets:
        if STAGE_buy_merge(pet.type, None):
            return True
    return False

def STAGE_buy_exchange(wanted_pet: ShopPetInfo):
    best = (6969, 6969)
    for i, pet in enumerate(G.player_info.pets):
        if pet and petMetric(pet) < best:
            best = petMetric(pet)
            to_sell = pet
            to_sell_i = i
    assert best != (6969, 6969)
    
    if best < petMetric(wanted_pet):
        bot_battle.sell_pet(getPet(to_sell))
        globals()["G"] = bot_battle.get_game_info()
        bot_battle.buy_pet(getPet(wanted_pet), to_sell_i)
        globals()["G"] = bot_battle.get_game_info()
        return True
    else:
        return False



def STAGE_freeze_pet():
    if G.player_info.coins == 0: return False
    
    shop_pets = G.player_info.shop_pets
    for shop_pet in shop_pets:
        want = petMetric(shop_pet)[0]
        if want > 0 and not shop_pet.is_frozen:
            bot_battle.freeze_pet(getPet(shop_pet))
            globals()["G"] = bot_battle.get_game_info()
            return True
    return False

def STAGE_buy_pet():
    if G.player_info.coins < 3: return False

    shop_pets = G.player_info.shop_pets
    assert all(shop_pet.cost == 3 for shop_pet in shop_pets)
    wanted_pets = sorted(shop_pets, key=petMetric, reverse=True)
    for wanted_pet in wanted_pets:
        want = petMetric(wanted_pet)[0]
        if want in [+1] and STAGE_buy_insert(wanted_pet): return True
        if want in [+1] and STAGE_buy_merge(wanted_pet.type, wanted_pet): return True
        if want in [+1] and STAGE_buy_merge_any() and STAGE_buy_insert(wanted_pet): return True
        if want in [+1] and STAGE_buy_exchange(wanted_pet): return True
    return False

# def STAGE_fill():
# #     if G.player_info.coins < 3: return False

#     shop_pets = G.player_info.shop_pets
#     assert all(shop_pet.cost == 3 for shop_pet in shop_pets)
#     wanted_pets = sorted(shop_pets, key=petMetric, reverse=True)
#     for wanted_pet in wanted_pets:
#         want = petMetric(wanted_pet)[0]
#         if want in [0, +1] and STAGE_buy_insert(wanted_pet): return True
#     return False

def STAGE_freeze_food():
    for food in G.player_info.shop_foods:
        if foodMetric(food) > 0 and not food.is_frozen:
            print("FREEZE FOOD", food)
            bot_battle.freeze_food(food)
            globals()["G"] = bot_battle.get_game_info()
            return True
    return False

def STAGE_buy_food():
    if G.player_info.coins < 3: return False
    
    for food in sorted(G.player_info.shop_foods, key=foodMetric, reverse=True):
        if foodMetric(food) <= 0: continue
        pets = sorted([pet for pet in G.player_info.pets if pet], key=AHMetric, reverse=True)
        for pet in pets:
            if food.is_frozen and pet and not pet.carried_food:
                print("BUY FOOD", food, getPet(pet))
                bot_battle.buy_food(getFood(food), getPet(pet))
                globals()["G"] = bot_battle.get_game_info()
                return True
    return False

def STAGE_unfreeze_all():
    for food in G.player_info.shop_foods:
        if food.is_frozen:
            bot_battle.unfreeze_food(getFood(food))
            globals()["G"] = bot_battle.get_game_info()
    for pet in G.player_info.shop_pets:
        if pet.is_frozen:
            bot_battle.unfreeze_pet(getPet(pet))
            globals()["G"] = bot_battle.get_game_info()
    return False

def AHMetric(shop_pet: ShopPetInfo):
    AH = shop_pet.health * shop_pet.attack
    return AH

# want is:
# -1 = dont want
# 0 = only get if empty space (stats boost until better pets)
# +1 = always good, would merge (long term strat)
def petMetric(shop_pet: ShopPetInfo):
    AH = shop_pet.health * shop_pet.attack
    if shop_pet.type in [PetType.BADGER, PetType.HEDGEHOG, PetType.ELEPHANT]:
        want = -2
    elif calc_sublevel(collectPets(shop_pet.type)) >= 5:
        want = -2
    elif G.round_num <= 6 and shop_pet.type == PetType.SWAN and not collectPets(PetType.SWAN):
        want = +1
    else:
        rating = {
            # tier 1
            PetType.FISH: +1, 
            # tier 2
            PetType.KANGAROO: +1,
            PetType.PEACOCK: +1,
            # tier 3 TODO: check this
            PetType.DOLPHIN: 0,
            # tier 4
            PetType.BISON: +1,
            PetType.BLOWFISH: +1,
            PetType.HIPPO: 0,
            PetType.PENGUIN: +1 if G.round_num <= 8 else 0
        }
        want = rating.get(shop_pet.type, -1)
    return (want, AH)

def foodMetric(food: ShopFoodInfo):
    if food.type in [FoodType.MEAT_BONE, FoodType.GARLIC, FoodType.PEAR, FoodType.CANNED_FOOD]:
        return +1
    else:
        return -1

def main():
    for round_num in count(1):
        assert round_num == G.round_num
        print("#" * 20, G.round_num, "#" * 20)
        print()
        print(G.player_info.shop_pets, G.player_info.shop_foods)
        
        STAGE_unfreeze_all()
        
        while G.player_info.coins >= 3:
            while STAGE_buy_pet(): continue
            while STAGE_buy_food(): continue
            if G.player_info.coins >= 4:
                bot_battle.reroll_shop()
                globals()["G"] = bot_battle.get_game_info()
                print(G.player_info.shop_pets, G.player_info.shop_foods)
            else:
                break

        while G.player_info.coins > 0:
            while STAGE_freeze_pet(): continue
            while STAGE_freeze_food(): continue
            bot_battle.reroll_shop()
            globals()["G"] = bot_battle.get_game_info()
            print(G.player_info.shop_pets, G.player_info.shop_foods)

        while STAGE_freeze_pet(): continue
        
        STAGE_perm()
        
        bot_battle.end_turn()
        globals()["G"] = bot_battle.get_game_info()


if __name__ == "__main__":
    main()
