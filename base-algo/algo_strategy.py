import gamelib
import random
import math
import warnings
from sys import maxsize
import json
from collections import deque, namedtuple
import copy
from gamelib.util import get_command
from gamelib.navigation import ShortestPathFinder

"""
Most of the algo code you write will be in this file unless you create new
modules yourself. Start by modifying the 'on_turn' function.

Advanced strategy tips: 

  - You can analyze action frames by modifying on_action_frame function

  - The GameState.map object can be manually manipulated to create hypothetical 
  board states. Though, we recommended making a copy of the map to preserve 
  the actual current map state.
"""

building = namedtuple('Building', ['name', 'x', 'y'])
attacker = namedtuple('Attacker', ['name', 'x', 'y', 'num'])

class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))

    def on_game_start(self, config):
        """ 
        Read in config and perform any initial setup here 
        """
        gamelib.debug_write('Configuring your custom algo strategy...')
        self.config = config
        global WALL, SUPPORT, TURRET, SCOUT, DEMOLISHER, INTERCEPTOR, MP, SP
        WALL = config["unitInformation"][0]["shorthand"]
        SUPPORT = config["unitInformation"][1]["shorthand"]
        TURRET = config["unitInformation"][2]["shorthand"]
        SCOUT = config["unitInformation"][3]["shorthand"]
        DEMOLISHER = config["unitInformation"][4]["shorthand"]
        INTERCEPTOR = config["unitInformation"][5]["shorthand"]
        MP = 1
        SP = 0
        # This is a good place to do initial setup
        self.scored_on_locations = []

    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
        gamelib.debug_write("Starting on_turn")
        game_state = gamelib.GameState(self.config, turn_state)
        # self.print_map(game_state)
        gamelib.debug_write("My Health: " + str(game_state.my_health) + " Enermy Health: " + str(game_state.enemy_health))
        gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(game_state.turn_number))
        game_state.suppress_warnings(True)  #Comment or remove this line to enable warnings.
        gamelib.debug_write('Starting base')
        self.base_strategy(game_state)
        gamelib.debug_write("Finished base")
        gamelib.debug_write('Calling submit turn')
        game_state.submit_turn()

    # Player 1 sees: [[4, 12], [5, 15], [7, 12], [8, 15], [10, 12], [11, 15], [13, 12], [14, 15], [16, 12], [17, 15], [19, 12], [20, 15], [22, 12], [23, 15]]

    """
    NOTE: All the methods after this point are part of the sample starter-algo
    strategy and can safely be replaced for your custom algo.
    """

    def print_map(self, game_state):
        gamelib.debug_write('Map:\n')
        for i in range(0,28):
            row_str = "|" 
            for j in range(0,28):
                if game_state.game_map.in_arena_bounds([i,j]):
                    if len(game_state.game_map[i,j]) > 0:
                        row_str += (str(game_state.game_map[i,j][0].player_index) + str(game_state.game_map[i,j][0].unit_type) + " " + str(int(game_state.game_map[i,j][0].health)) + (5-len(str(game_state.game_map[i,j][0].unit_type) + str(game_state.game_map[i,j][0].health))) * " ")
                    else: 
                        row_str += "       "
                else:
                    row_str += "-------"
            gamelib.debug_write(row_str)

    def base_strategy(self, game_state):
        """
        For defense we will use a spread out layout and some interceptors early on.
        We will place turrets near locations the opponent managed to score on.
        For offense we will use long range demolishers if they place stationary units near the enemy's front.
        If there are no stationary units to attack in the front, we will send Scouts to try and score quickly.
        """

         # Examine exactly what I can see at the moment:
        list_of_buildings = []
        for i in range(0,28):
            for j in range(0,28):
                if game_state.game_map.in_arena_bounds([i,j]) and game_state.contains_stationary_unit([i,j]):
                    list_of_buildings.append([i,j])

        # gamelib.debug_write("Building List: "+ str(list_of_buildings))
        
        # Build 5 simple defences and upgrade them
        # game_state.attempt_spawn(TURRET, turret_locations)
        # game_state.attempt_upgrade(turret_locations)

        # Deploy a stack of scouts at the back.
        # if(game_state.turn_number >= 2):
        #     game_state.attempt_spawn(TURRET, turret_locations)
        # game_state.attempt_spawn(INTERCEPTOR, [[13, 0]], num=game_state.number_affordable(INTERCEPTOR))
        # game_state.attempt_spawn(WALL, [[14, 6]])
        # game_state.attempt_upgrade([14, 6])
        # game_state.attempt_remove([14, 6])

        game_state.attempt_spawn(SCOUT, [[13, 0]], num=game_state.number_affordable(SCOUT))
    
    
    def read_oppo_play(self, game_state):

        game_state_rollout = copy.deepcopy(game_state)
        game_state_rollout.submit_turn()
        game_state_string = get_command()
        current_state_as_dict = json.loads(game_state_string)
        gamelib.debug_write(current_state_as_dict)
    

    def on_action_frame(self, turn_string):
        """
        This is the action frame of the game. This function could be called 
        hundreds of times per turn and could slow the algo down so avoid putting slow code here.
        Processing the action frames is complicated so we only suggest it if you have time and experience.
        Full doc on format of a game frame at in json-docs.html in the root of the Starterkit.
        """
        # Let's record at what position we get scored on
        state = json.loads(turn_string)

        # next_game_state = gamelib.GameState(self.config, turn_string)
        # self.print_map(next_game_state)

        events = state["events"]
        breaches = events["breach"]
        for breach in breaches:
            location = breach[0]
            unit_owner_self = True if breach[4] == 1 else False
            # When parsing the frame data directly, 
            # 1 is integer for yourself, 2 is opponent (StarterKit code uses 0, 1 as player_index instead)
            if not unit_owner_self:
                gamelib.debug_write("Got scored on at: {}".format(location))
                self.scored_on_locations.append(location)
                gamelib.debug_write("All locations: {}".format(self.scored_on_locations))


if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
