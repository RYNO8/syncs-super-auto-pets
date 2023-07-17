# Orderings
pets which have abilities on "friend summoned" are at the back
pets which have friendly abilities are at the very front?
pets which have abilities of the form "when attacked, attack" are next at the front?

# Base stats
if I have pet with A attack and H health
and opponent has pet with a attack and h health
my pet lasts ceil(H/a) rounds and opponent's pet lasts ceil(h/A) rounds
I want H/a >>>> h/A, so i want to maximise AH
Tier 1: max AH = 6
Tier 2: max AH = 10
Tier 3: max AH = 21 (H = 7)
Tier 4: max AH = 20 (H = 5)
maybe health is more important for higher tiers because snipers

# Misc
Strategy is independant of opponents revealed strat?
Strategy is deterministic (sorry Peter). Choose based on most common opponent strat
Simulate games against different builds (all different builds with up to tier 3 pets ~4mil)
Submission uploads can be 50 MB :)
I thought of cracking python random, but i need 600+ 32 bit integers (also I dont see the results of all random generated data)
Pet id's are sequential, missing id means that a player has played "before" you at the same round, and has seen pets in the shop. probably this is a multiple of 5, which would be (num players before you + total rerolls before you)

# Reroll
only after settling on pet allocation and order
solving: if reroll costs $1, which gives you n options of cost C_i value V_i
strat to get highest value with $D
dp with store backtrack

# Pets
Tier 1: 7
Tier 2: 7
Tier 3: 9
Tier 4: 6

# Solved for small number of states
u^T A v thing, solve using scipy

# Strat 1
Manual genetic algo

# Strat 2
Minimax depth 1, simulate by copying engine and run different actions against many random opponent actions

# Strat 3
Elephant (Tier 3), Camel (Tier 3),                     Kangaroo (Tier 2)
                                    Peacock? (Tier 2),                   Bunny (Tier 3), Bunny (Tier 3)
food goes to                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Bison (Tier 4), Kangaroo (Tier 2), lvl 3 Fish

# Strat 4
evaluated based on future stats, chose moves to maximise evaluation

# Strat 5
P1 of https://syncs.org.au/competition/game/history/315853

# mkfifo fix
```
sudo umount /mnt/d && sudo mount -t drvfs D: /mnt/d -o metadata
```
