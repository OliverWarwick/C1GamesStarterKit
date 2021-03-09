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
        self.enum_to_index_map = {WALL: 0, SUPPORT: 1, TURRET: 2, SCOUT:3, DEMOLISHER:4, INTERCEPTOR:5}
        MP = 1
        SP = 0
        # This is a good place to do initial setup
        self.scored_on_locations = []
        # Varible to track whether we are in a state to play thunder or not. -1 = not ready/reset state , 0 = ready, 1 = played.
        self.play_thunder = -1

        # Set up queue structure
        '''
        structure_queue: deque[building]. Holds the structure we want to build. Deqeue as we can prepend
        when we need to fix up defenses. Also can be used for upgrades.
        building: namedtuple. Structure for holding instructions on what to build.
                  name - wall, turrent, upgrade. 
                  x / y - coordinates
        Any function using this will need to deal with the case where we have upgrades.
        '''
        self.structure_queue = deque()

        # Walls first
        wall_list = [[0, 13], [1, 13], [25, 13], [26, 13], [27, 13], [3, 12], [24, 12], [4, 11], [23, 11], [5, 10], [6, 9], [21, 9], [7, 8], [20, 8], [8, 7], [19, 7], [9, 6], [18, 6], [10, 5], [17, 5], [11, 4], [12, 4], [13, 4], [14, 4], [15, 4], [16, 4]]
        for [x1,y1] in wall_list:
            self.structure_queue.append(building(name=WALL, x=x1, y=y1))

        turrent_list = [[2, 13], [3, 13], [4, 12], [21, 12], [22, 11], [20, 10]]
        for [x1,y1] in turrent_list:
            self.structure_queue.append(building(name=TURRET, x=x1, y=y1))

        # support_list = [[14, 2]]
        # for [x1,y1] in support_list:
        #     self.structure_queue.append(building(name=SUPPORT, x=x1, y=y1))

        self.critcal_infra = [building(name=WALL, x=ele[0], y=ele[1]) for ele in [[0, 13], [1, 13], [3, 12], [24, 12], [4, 11], [23, 11], [5, 10], [6, 9], [21, 9], [7, 8], [20, 8], [8, 7], [19, 7], [9, 6], [18, 6], [10, 5], [17, 5], [11, 4], [12, 4], [13, 4], [14, 4], [15, 4], [16, 4]]] + [building(name=TURRET, x=ele[0], y=ele[1]) for ele in turrent_list] 
        # non_critcal = [building(name=WALL, x=25, y=13), building(name=WALL, x=26, y=13), building(name=WALL, x=27, y=13), building(name=WALL, x=28, y=10)]
        # for ele in self.critcal_infra:
        #     if ele in non_critcal:
        #         self.critcal_infra.remove(ele)
        gamelib.debug_write('Critcal Infra: ' + str(self.critcal_infra))

        # Recording of which building we had in the previous iteration.
        ''' Has the form set(tuple(name, x, y)) so these need unpacking when using - needs to be this way so we can hash the elements unlike lists. '''
        self.last_round_stationary_units = set()

    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
        state = json.loads(turn_state)
        stateType = int(state.get("turnInfo")[0])
        gamelib.debug_write('Original State Value: ' + str(stateType))
        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(game_state.turn_number))
        game_state.suppress_warnings(True)  #Comment or remove this line to enable warnings.
        self.starter_strategy(game_state)
        game_state.submit_turn()


    """
    NOTE: All the methods after this point are part of the sample starter-algo
    strategy and can safely be replaced for your custom algo.
    """

    def starter_strategy(self, game_state):
        """
        For defense we will use a spread out layout and some interceptors early on.
        We will place turrets near locations the opponent managed to score on.
        For offense we will use long range demolishers if they place stationary units near the enemy's front.
        If there are no stationary units to attack in the front, we will send Scouts to try and score quickly.
        """
        gamelib.debug_write('Performing starter stratergy {} of your custom algo strategy'.format(game_state.turn_number))

        gamelib.debug_write('Previous stationary units - pre call: ' + str(self.last_round_stationary_units))

        if game_state.turn_number == 0:
            # Build defences
            self.build_intial_defences(game_state)
            # Create attack
            self.play_inital_attack(game_state)
        else:
            # Build defences - first rebuild what we lost and then add to what we have
            self.repair_critcal_items(game_state)
            self.queue_rebuild_lost_defenses(game_state)

            gamelib.debug_write('Current Queue: ' + str(self.structure_queue[0]))

            self.build_new_defences(game_state)

            # Create attack.
            # if self.should_thunder_strike(game_state) and self.play_thunder == -1:
            #     self.prepare_thunder_attack(game_state)
            #     self.play_thunder = 0
            # elif self.play_thunder == 0:
            #     self.play_thunder_strike(game_state)
            #     self.play_thunder = 1
            # elif self.play_thunder == 1:
            #     self.rebuild_after_thunder_strike(game_state)
            #     self.play_thunder = -1
            # else:
            #     # Pick standard attack.
            #     # self.play_standard_attack(game_state)
            #     our_attackers = [attacker(name=SCOUT, x=11, y=2, num=game_state.number_affordable(SCOUT))]
            #     self.roll_out_attackers_play(game_state, our_attackers, [])

            our_attackers = [attacker(name=SCOUT, x=11, y=2, num=game_state.number_affordable(SCOUT))]
            our_buildings = [building(name=TURRET, x=13, y=13)]
            gamelib.debug_write('Previous number of scouts afffordable: {}'.format(game_state.number_affordable(SCOUT)))

            self.roll_out_attackers_play(game_state, our_attackers, our_buildings)
            gamelib.debug_write('Current energy health points: {}'.format(game_state.enemy_health))
            gamelib.debug_write('Current number of scouts afffordable: {}'.format(game_state.number_affordable(SCOUT)))
            for att in our_attackers:
                game_state.attempt_spawn(SCOUT, locations=[[11,2]], num=game_state.number_affordable(SCOUT))

        # Last call of the round which is used to figure out what was destroyed.
        self.last_round_stationary_units = self.get_current_stationary_units(game_state)
        gamelib.debug_write('Previous stationary units - post call: ' + str(self.last_round_stationary_units))


    def roll_out_attackers_play(self, game_state, our_new_attackers_list, our_new_builings_list):
        ''' 
        This will simulate a roll out of the attackers once place. 
        This assume at the moment that the map hasn't been altered.
        our_new_attackers_list: List[attacker] where attacker is a named tuple of (name, x, y, num)
        our_new_builings_list: List[building] where building is a named tuple of (name, x, y)

        Current assuming we are the second player to move.
        '''

        # TODO - Figure out whether it matters if you're player 1 or not.
        # TODO - Add oppo agents in the case we're player 1, or two.

        gamelib.debug_write("\n\nSTART OF ROLL OUT")
        gamelib.debug_write("Game State current turn number: " + str(game_state.turn_number))

        # Info about the current turn number
        current_state_as_dict = json.loads(game_state.serialized_string)
        turn_info = current_state_as_dict["turnInfo"]
        gamelib.debug_write("Turn Info of original game before:  " + str(turn_info))
        gamelib.debug_write(current_state_as_dict)

        # Create a copy of the game_state so we can modify it.
        game_state_rollout = copy.deepcopy(game_state)
        # Place our attackers
        for a in our_new_attackers_list:
            game_state_rollout.attempt_spawn(unit_type=a.name, locations=[[a.x, a.y]], num=a.num)
        # Place our buildings.
        for b in our_new_builings_list:
            game_state_rollout.attempt_spawn(unit_type=b.name, locations=[[b.x, b.y]])
        
        # Simulate on_turn.
        gamelib.debug_write("Submitting turn")
        game_state_rollout.submit_turn()
        #game_state_rollout.submit_turn()

        # Turn info after sumbitting turn.
        current_state_as_dict = json.loads(game_state_rollout.serialized_string)
        turn_info = current_state_as_dict["turnInfo"]
        gamelib.debug_write("Turn Info after submitting turn:  " + str(turn_info))

        # Wait for the result of the run.
        gamelib.debug_write("Getting from turn")
        game_state_string = get_command()

        # Turn info after sumbitting turn.
        current_state_as_dict = json.loads(game_state_string)
        turn_info = current_state_as_dict["turnInfo"]
        gamelib.debug_write("Turn Info after get command:  " + str(turn_info))

        # TODO - if statement to figure out if we need to then replicate a call from an oppo

        state = json.loads(game_state_string)
        stateType = int(state.get("turnInfo")[0])
        # gamelib.debug_write("State Type: " + str(stateType))

        while stateType == 1:
            game_state_string = get_command()
            next_state = json.loads(game_state_string)
            stateType = int(next_state.get("turnInfo")[0])

            turn_info = next_state["turnInfo"]
            gamelib.debug_write("Turn Info after while get:  " + str(turn_info))
            

        # State to string: dict_keys(['p2Units', 'turnInfo', 'p1Stats', 'p1Units', 'p2Stats', 'events'])
        # Get output of the simulation.
        # end_state = next_state
        gamelib.debug_write("Finished the round. OW")
        gamelib.debug_write("State to string: " + str(next_state.keys()))
        gamelib.debug_write("turnInfo: " + str(next_state['turnInfo']))
        gamelib.debug_write("p1units: " + str(next_state['p1Units']))
        gamelib.debug_write("p2units: " + str(next_state['p2Units']))
        gamelib.debug_write("p1stats: " + str(next_state['p1Stats']))
        gamelib.debug_write("p2stats: " + str(next_state['p2Stats']))
        gamelib.debug_write("events: " + str(next_state['events']))
        gamelib.debug_write("Predicted next round health: " + str(next_state['p2Stats'][0]))
        gamelib.debug_write("StateType: " + str(int(next_state.get("turnInfo")[0])))

        next_game_state = gamelib.GameState(self.config, game_state_string)
        gamelib.debug_write("Roll out states health predictor: " + str(next_game_state.enemy_health))

        gamelib.debug_write("Game State current turn number: " + str(game_state.turn_number))

        # Ensure original is the same.
        current_state_as_dict = json.loads(game_state.serialized_string)
        turn_info = current_state_as_dict["turnInfo"]
        gamelib.debug_write("Turn Info of original afterwards  " + str(turn_info))



        # # for att in oppo_attackers_list:
        # #     game_state_rollout.attempt_spawn(unit_type=att.name, locations=[[att.x, att.y]], num=att.num)

        # gamelib.debug_write("Before Turn number " + str(game_state.turn_number))

        # # StateType = 0.
        # gamelib.debug_write("Submitting turn")
        # game_state_rollout.submit_turn()

        # # Wait for the result of the run.
        # gamelib.debug_write("Getting from turn")
        # game_state_string = get_command()

        # # In the algo core version we have
        # if "turnInfo" in game_state_string:
        #     state = json.loads(game_state_string)
        #     gamelib.debug_write("State to string: " + str(state.keys()))
        #     gamelib.debug_write("turnInfo: " + str(state['turnInfo']))
        #     gamelib.debug_write("p1units: " + str(state['p1Units']))
        #     gamelib.debug_write("p2units: " + str(state['p2Units']))
        #     gamelib.debug_write("events: " + str(state['events']))

        #     stateType = int(state.get("turnInfo")[0])
        #     gamelib.debug_write("State Type: " + str(stateType))

        #     if stateType == 0:
        #         # self.on_turn(game_state_string)
        #         # Recover the game state:
        #         updated_game_state = gamelib.GameState(self.config, game_state_string)
        #         gamelib.debug_write("After Turn number " + str(updated_game_state.turn_number))


        #         # Then try and yield info.
        #     elif stateType == 1:
        #         # self.on_action_frame(game_state_string)
        #         updated_game_state = gamelib.GameState(self.config, game_state_string)
        #         gamelib.debug_write("After Turn number " + str(updated_game_state.turn_number))
        #         state = json.loads(game_state_string)
        #         events = state["events"]
        #         breaches = events["breach"]
        #         gamelib.debug_write("Olly Debug")
        #         for breach in breaches:
        #             location = breach[0]
        #             unit_owner_self = True if breach[4] == 1 else False
        #             # When parsing the frame data directly, 
        #             # 1 is integer for yourself, 2 is opponent (StarterKit code uses 0, 1 as player_index instead)
        #             if not unit_owner_self:
        #                 gamelib.debug_write("Olly - Got scored on at: {}".format(location))
        #                 self.scored_on_locations.append(location)
        #                 gamelib.debug_write("Olly - All locations: {}".format(self.scored_on_locations))
        #             else:
        #                 gamelib.debug_write("Olly - Scored on oppo: {}".format(location))
            
        #     if stateType == 0 or stateType == 1:
        #         gamelib.debug_write('Old Resource : {}  New resources: {}'.format(game_state.get_resource(MP), updated_game_state.get_resource(MP)))
        #         gamelib.debug_write('Before enermy health {}  After energy health: {}'.format(game_state.enemy_health, updated_game_state.enemy_health))

        #     # Run another get command. See what we get this time.
        #     while stateType == 1:
        #         gamelib.debug_write("Blip")
        #         game_state_string = get_command()
        #         next_state = json.loads(game_state_string)
        #         stateType = int(next_state.get("turnInfo")[0])

        #     gamelib.debug_write("Final state")
        #     # game_state_string = get_command()
        #     # next_state = json.loads(game_state_string)
        #     # stateType = int(next_state.get("turnInfo")[0])
            
           



        # # if "turnInfo" in game_state_string:
        # #     gamelib.debug_write("Updated State Value: " + str(stateType))
        # #     # StateType is now 1.
        # #     self.on_action_frame(game_state_string)
        # #     new_state = gamelib.GameState(self.config, game_state_string)
            
        # #     gamelib.debug_write('Old Resource : {}  New resources: {}'.format(game_state.get_resource(MP), new_state.get_resource(MP)))

            # list_of_old_buildings = []
            # list_of_new_buildings = []
            # for i in range(0,28):
            #     for j in range(0,28):
            #         if game_state.game_map.in_arena_bounds([i,j]) and game_state.contains_stationary_unit([i,j]):
            #             list_of_old_buildings.append([i,j])
            #         if new_state.game_map.in_arena_bounds([i,j]) and new_state.contains_stationary_unit([i,j]): 
            #             list_of_new_buildings.append([i,j])

            # if(len(list_of_old_buildings) != len(list_of_new_buildings)):
            #     gamelib.debug_write('Old Buildings : {}  \nNew buildings: {}'.format(str(list_of_old_buildings), str(list_of_new_buildings)))
            
        # #     gamelib.debug_write('Before enermy health {}  After energy health: {}'.format(game_state.enemy_health, new_state.enemy_health))

        # #     gamelib.debug_write('Old Map:\n')
        # #     for i in range(0,28):
        # #         row_str = "" 
        # #         for j in range(0,28):
        # #             if game_state.game_map.in_arena_bounds([i,j]):
        # #                 if len(game_state.game_map[i,j]) > 0:
        # #                     row_str += (str(game_state.game_map[i,j][0].player_index) + str(game_state.game_map[i,j][0].unit_type) + " " + str(game_state.game_map[i,j][0].health) + (7-len(str(game_state.game_map[i,j][0].unit_type) + str(game_state.game_map[i,j][0].health))) * " ")
        # #                     # gamelib.debug_write(type(new_state.game_map[i,j][0]))
        # #                 else: 
        # #                     row_str += "         "
        # #             else:
        # #                 row_str += "---------"
        # #         gamelib.debug_write(row_str)


        # #     gamelib.debug_write('New Map:\n')
        # #     for i in range(0,28):
        # #         row_str = "" 
        # #         for j in range(0,28):
        # #             if new_state.game_map.in_arena_bounds([i,j]):
        # #                 if len(new_state.game_map[i,j]) > 0:
        # #                     row_str += (str(new_state.game_map[i,j][0].player_index) + str(new_state.game_map[i,j][0].unit_type) + " " + str(new_state.game_map[i,j][0].health) + (7-len(str(new_state.game_map[i,j][0].unit_type) + str(new_state.game_map[i,j][0].health))) * " ")
        # #                     # gamelib.debug_write(type(new_state.game_map[i,j][0]))
        # #                 else: 
        # #                     row_str += "         "
        # #             else:
        # #                 row_str += "---------"
        # #         gamelib.debug_write(row_str)

        # # Check how the game map has now changed.
        # # original_game_map = game_state.game_map.__dict__
        # # # gamelib.debug_write('Game map of original: ' + str(original_game_map['_GameMap__map'][0]))
        # # roll_out_game_map = game_state_rollout.game_map.__dict__
        # # # gamelib.debug_write('Game map of roll_out: ' + str(roll_out_game_map['_GameMap__map'][0]))
        # # for i in range(0, len(original_game_map['_GameMap__map'])):
        # #     for j in range(0, len(original_game_map['_GameMap__map'][i])):
        # #         if(original_game_map['_GameMap__map'][i][j] != roll_out_game_map['_GameMap__map'][i][j]):
        # #             gamelib.debug_write(str(i) + " " + str(j))
        # #             gamelib.debug_write('Game map of original: ' + str(original_game_map['_GameMap__map'][i][j]))
        # #             gamelib.debug_write('Game map of rollout: ' + str(roll_out_game_map['_GameMap__map'][i][j]))




    def build_intial_defences(self, game_state):
        """
        Build basic defenses using hardcoded locations.
        Remember to defend corners and avoid placing units in the front where enemy demolishers can attack them.
        """
        # Useful tool for setting up your base locations: https://www.kevinbai.design/terminal-map-maker
        # More community tools available at: https://terminal.c1games.com/rules#Download

        # Get my own points.
        gamelib.debug_write('Queue size: {}'.format(len(self.structure_queue)))

        # Place the inital defenses.
        while(len(self.structure_queue) > 0 and game_state.get_resource(resource_type=SP, player_index=0) > 0):
            gamelib.debug_write('Number of SP: {}'.format(game_state.get_resource(resource_type=SP, player_index=0)))
            placement = self.structure_queue.popleft()
            number_placed = game_state.attempt_spawn(placement.name, [placement.x, placement.y])
            gamelib.debug_write('Attempting to spawn {} at location ({}, {}). Number placed: {}'.format(placement.name, placement.x, placement.y, number_placed))

        # Add to the queue the things we want to upgrade and build next.
        turrents_to_add = [[24, 13], [20, 12], [22, 12], [23, 12], [5, 11], [19, 10]]
        for tur in turrents_to_add:
            self.structure_queue.append(building(name=TURRET, x=tur[0], y=tur[1]))

        # RHS turrents then walls.
        upgrades = [[20, 12], [21, 12], [22, 12], [24, 13], 
                    [25, 13], [26, 13], [27, 13]]
        
        for up in upgrades:
            self.structure_queue.append(building(name="upgrade", x= up[0], y=up[1]))

        # TODO - Come up with some logic about how to decide what to put next.
        

        # Extra turrents on the RHS and LHS.
        extra_def = [[23, 13], [1, 12], [2, 12], [18, 12], [19, 12], [3, 11], [18, 10], [19, 10], [20, 9]]
        for new_def in extra_def:
            self.structure_queue.append(building(name=TURRET, x=new_def[0], y=new_def[1]))
        
        # Extra walls on RHS to draw damage.
        extra_walls = [[17, 13], [18, 13], [19, 13], [20, 13], [17, 12], [16, 10], [17, 10]]
        for new_wall in extra_walls:
            self.structure_queue.append(building(name=WALL, x=new_wall[0], y=new_wall[1]))
        
        # Update extra defenses
        for new_def in extra_def:
            self.structure_queue.append(building(name="upgrade", x=new_def[0], y=new_def[1]))

        # Add more supports now
        extra_supp = [[17, 6], [16, 5], [12, 3], [13, 2]]
        for new_supp in extra_supp:
            self.structure_queue.append(building(name=SUPPORT, x=new_supp[0], y=new_supp[1]))
        
        # Update extra support
        for new_def in extra_def + extra_walls + extra_supp:
            self.structure_queue.append(building(name="upgrade", x=new_def[0], y=new_def[1]))

        # Then just flood with defenses
        flood_def = [[19, 13], [20, 13], [21, 13], [17, 12], [19, 12], [17, 11], [17, 10]]
        for f_def in flood_def:
            self.structure_queue.append(building(name=TURRET, x=f_def[0], y=f_def[1]))

        # Update extra defenses
        for f_def in flood_def:
            self.structure_queue.append(building(name="upgrade", x=f_def[0], y=f_def[1]))

    
    def repair_critcal_items(self, game_state):
        # We can just attempt to build here and if we are unseccesful it's because the server rejects any double laying which is dine by us.
        for b in self.critcal_infra:
            game_state.attempt_spawn(b.name, [b.x, b.y])
        for b in self.critcal_infra:
            game_state.attempt_upgrade([b.x, b.y])


    def build_new_defences(self, game_state):

        ''' 
        This should take way is on the queue and build with it / upgrade it
        '''
        gamelib.debug_write('Queue size: {}'.format(len(self.structure_queue)))

        # Place the inital defenses.
        number_placed = 1
        # Check whether we have enough to place the next item (lazy eval so fine).
        # This should stop things being popped off the queue and not being built.
        while(number_placed > 0 and len(self.structure_queue) > 0 and game_state.get_resource(resource_type=SP, player_index=0) > 0):
            gamelib.debug_write('Number of SP: {}'.format(game_state.get_resource(resource_type=SP, player_index=0)))
            placement = self.structure_queue.popleft()
            # Need to careful here whether we decide to upgrade or build a new defence.
            if(placement.name == 'upgrade'):
                number_placed = game_state.attempt_upgrade([placement.x, placement.y])
            else: 
                number_placed = game_state.attempt_spawn(placement.name, [placement.x, placement.y])
            
            if number_placed == 0:
                # Need to add back into the queue.
                self.structure_queue.appendleft(placement)

            gamelib.debug_write('Attempting to spawn {} at location ({}, {}). Number placed: {}'.format(placement.name, placement.x, placement.y, number_placed))


    def queue_rebuild_lost_defenses(self, game_state):

        '''
        Identify the buildings which were lost in the previous round and then place onto the queue
        and attempt to upgrade these
        '''

        rebuild_list = self.find_destroyed_buildings(game_state)

        # DO NOT REPLACE LIST: Thunderstrike.
        non_replacements = {(WALL, 25, 13), (WALL, 26, 13), (WALL, 27, 13), (WALL, 21, 10)}
        rebuild_list = rebuild_list - non_replacements
        gamelib.debug_write('Thunderstike, saving wall: ' + str(rebuild_list - non_replacements))
        gamelib.debug_write('Rebuild list' + str(rebuild_list))
            
        # Use this as a heuristic to upgrade these buildings are they are likely to be attacked again. 
        # When pushing in from the left need to ensure we do in in backwards order.
        for item in rebuild_list:
            self.structure_queue.appendleft(building(name='upgrade', x=item[1], y=item[2]))

        for item in rebuild_list:
            self.structure_queue.appendleft(building(name=item[0], x=item[1], y=item[2]))


    def play_inital_attack(self, game_state):

        # Place a double interceptor halfway up the right hand side in order to tackle anything inbound.
        deploy_location = [20,6]
        game_state.attempt_spawn(INTERCEPTOR, deploy_location, 2)



    def play_standard_attack(self, game_state):

        '''
        Just a normal attack using 2 scouts, more to see if we can do damage and expliot weekness
        '''
        # if(game_state.get_resource(resource_type=MP, player_index=0) > 8 and game_state.turn_number % 4 == 0):
        #     game_state.attempt_spawn(DEMOLISHER, [[11, 2]], 1)
        game_state.attempt_spawn(SCOUT, [11, 2], game_state.number_affordable(SCOUT))




    def should_thunder_strike(self, game_state):
        # TODO - Add logic with number of MP.

        return (game_state.get_resource(resource_type=MP, player_index=0) > 20 and game_state.get_resource(resource_type=SP, player_index=0) >= 5)


    def prepare_thunder_attack(self, game_state):
        # Remove the walls.
        walls_to_remove = [25, 13], [26, 13], [27, 13]
        game_state.attempt_remove(walls_to_remove)

        # Try to add supports if possible:
        supports = [[13, 3], [14, 3], [13, 2], [14, 2]]
        num_build_succ = game_state.attempt_spawn(SUPPORT, supports)
        num_upgrade_succ = game_state.attempt_upgrade(supports)

        if (num_build_succ == 0 and num_upgrade_succ == 0):
            # Attempt to build extra ones.
            extra_supports = [[17, 6], [16, 5], [12, 3], [13, 2]]
            num_build_succ = game_state.attempt_spawn(SUPPORT, extra_supports)
            num_upgrade_succ = game_state.attempt_upgrade(extra_supports)
       



    def rebuild_after_thunder_strike(self, game_state):

        # Replace the front 3 walls. 
        walls_to_replace = [25, 13], [26, 13], [27, 13]
        game_state.attempt_spawn(WALL, walls_to_replace)
        game_state.attempt_upgrade(walls_to_replace)

        # Remove the blocking piece.
        game_state.attempt_remove([[22, 10]])


    def play_thunder_strike(self, game_state):

        '''
        This is the play in which we remove the blocking tiles and then charge with scouts / demolisher
        '''

        # TODO - Need to write this so it's varible.

        # Block of the path so we head straight for the RHS.
        game_state.attempt_spawn(WALL, locations=[[22, 10]])

        # Place an demolisher up the RHS to start.
        # game_state.attempt_spawn(DEMOLISHER, locations=[[17, 3]], num=2)

        # Scouts, use as many as we can afford.
        game_state.attempt_spawn(SCOUT, locations=[12, 1], num=5)
        game_state.attempt_spawn(SCOUT, locations=[11, 2], num=int(game_state.get_resource(resource_type=MP, player_index=0) - 5))

        # TODO - In future we should optimise this for weather we will get blocked, and how much we can risk etc.

        # Interceptor to clean up afterwards.
        # game_state.attempt_spawn(INTERCEPTOR, locations=[[14, 0]], num=2)

        game_state.attempt_remove([[22, 10]])
     






    

    def stall_with_interceptors(self, game_state):
        """
        Send out interceptors at random locations to defend our base from enemy moving units.
        """
        # We can spawn moving units on our edges so a list of all our edge locations
        friendly_edges = game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_LEFT) + game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_RIGHT)
        
        # Remove locations that are blocked by our own structures 
        # since we can't deploy units there.
        deploy_locations = self.filter_blocked_locations(friendly_edges, game_state)
        
        # While we have remaining MP to spend lets send out interceptors randomly.
        while game_state.get_resource(MP) >= game_state.type_cost(INTERCEPTOR)[MP] and len(deploy_locations) > 0:
            # Choose a random deploy location.
            deploy_index = random.randint(0, len(deploy_locations) - 1)
            deploy_location = deploy_locations[deploy_index]
            game_state.attempt_spawn(INTERCEPTOR, deploy_location)
            """
            We don't have to remove the location since multiple mobile 
            units can occupy the same space.
            """

    def demolisher_line_strategy(self, game_state):
        """
        Build a line of the cheapest stationary unit so our demolisher can attack from long range.
        """
        # First let's figure out the cheapest unit
        # We could just check the game rules, but this demonstrates how to use the GameUnit class
        stationary_units = [WALL, TURRET, SUPPORT]
        cheapest_unit = WALL
        for unit in stationary_units:
            unit_class = gamelib.GameUnit(unit, game_state.config)
            if unit_class.cost[game_state.MP] < gamelib.GameUnit(cheapest_unit, game_state.config).cost[game_state.MP]:
                cheapest_unit = unit

        # Now let's build out a line of stationary units. This will prevent our demolisher from running into the enemy base.
        # Instead they will stay at the perfect distance to attack the front two rows of the enemy base.
        for x in range(27, 5, -1):
            game_state.attempt_spawn(cheapest_unit, [x, 11])

        # Now spawn demolishers next to the line
        # By asking attempt_spawn to spawn 1000 units, it will essentially spawn as many as we have resources for
        game_state.attempt_spawn(DEMOLISHER, [24, 10], 1000)

    def least_damage_spawn_locations(self, game_state, location_options, number_of_returns):
        """
        This function will help us guess which location is the safest to spawn moving units from.
        It gets the path the unit will take then checks locations on that path to 
        estimate the path's damage risk.
        """
        location_damage_map = {}
        # Get the damage estimate each path will take
        for location in location_options:
            path = game_state.find_path_to_edge(location)
            damage = 0
            for path_location in path:
                # Get number of enemy turrets that can attack each location and multiply by turret damage
                damage += len(game_state.get_attackers(path_location, 0)) * gamelib.GameUnit(TURRET, game_state.config).damage_i

            location_damage_map[location] = damage

        # Sort by the values in decendending order, get the first N many values and then get the locations of these.
        return [y[0] for y in sorted(location_damage_map.items(), key=lambda x: x[1])[0:number_of_returns]]

    def get_current_stationary_units(self, game_state):
        '''
        returns a list of our stationary units in the form [type, [location_x, location_y]]
        Used for keeping track of what was destroyed in the previous round
        '''
        stationary_units = set()
        for location in game_state.game_map:
            if game_state.contains_stationary_unit(location):
                for unit in game_state.game_map[location]:
                    if unit.player_index == 0:
                        stationary_units.add((unit.unit_type, location[0], location[1]))
        return stationary_units
                        

    def find_destroyed_buildings(self, game_state):
        ''' 
        returns locations and what was destroyed in the form [type, [location_x, location_y]]
        Used to figure out what was lost between this round and the last round.
        '''
        current_stationary_units = self.get_current_stationary_units(game_state)
        gamelib.debug_write('Current Station Units: ' + str(current_stationary_units))
        gamelib.debug_write('Last rounds stationary Units: ' + str(self.last_round_stationary_units))
        gamelib.debug_write('Diffence: ' + str(set(self.last_round_stationary_units) - set(current_stationary_units)))
        return self.last_round_stationary_units - current_stationary_units


    def detect_enemy_unit(self, game_state, unit_type=None, valid_x = None, valid_y = None):
        total_units = 0
        for location in game_state.game_map:
            if game_state.contains_stationary_unit(location):
                for unit in game_state.game_map[location]:
                    if unit.player_index == 1 and (unit_type is None or unit.unit_type == unit_type) and (valid_x is None or location[0] in valid_x) and (valid_y is None or location[1] in valid_y):
                        total_units += 1
        return total_units
        
    def filter_blocked_locations(self, locations, game_state):
        filtered = []
        for location in locations:
            if not game_state.contains_stationary_unit(location):
                filtered.append(location)
        return filtered

    def on_action_frame(self, turn_string):
        """
        This is the action frame of the game. This function could be called 
        hundreds of times per turn and could slow the algo down so avoid putting slow code here.
        Processing the action frames is complicated so we only suggest it if you have time and experience.
        Full doc on format of a game frame at in json-docs.html in the root of the Starterkit.
        """
        # Let's record at what position we get scored on
        state = json.loads(turn_string)
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
