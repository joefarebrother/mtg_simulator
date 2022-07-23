import game
from players import *
from cards import *
from actions import start_game, do_turn

p0 = UserPlayer("Human")
p1 = Aggressive("Goldfish")

build_deck(p0, [forest, grizzly_bears, reclaim,
                black_lotus, chronomaton, lightning_bolt, zap, tim, memnite])

build_deck(p1, [forest]*5+[grizzly_bears, memnite])

start_game()

try:
    while True:
        do_turn()
except game.GameOver:
    print(f"Game over; {game.winner} wins")
