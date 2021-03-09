import gamelib
import random
import math
import warnings
from sys import maxsize
import json
import copy
from gamelib.util import get_command
from collections import deque, namedtuple
from queue import PriorityQueue




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
        self.saved_game_state = None


        self.p_queue = PriorityQueue()          # Should be of the form: (float, building)

        self.critical_walls = [[2, 13], [3, 12], [23, 12], [4, 11], [5, 10], [6, 9], [7, 8], [19, 8], [8, 7], [18, 7], [9, 6], [17, 6], [10, 5], [16, 5], [11, 4], [15, 4], [12, 3], [13, 3], [14, 3], [0, 13], [1, 13], [25, 13], [26, 13], [27, 13]]
        self.critical_turrents = [[3, 13], [24, 13], [4, 12], [22, 12], [21, 11], [22, 11], [19, 9], [20, 9]]

        self.thunder_critical_infra = [[2, 13], [3, 12], [23, 12], [4, 11], [5, 10], [6, 9], [7, 8], [19, 8], [8, 7], [18, 7], [9, 6], [17, 6], [10, 5], [16, 5], [11, 4], [15, 4], [12, 3], [13, 3], [14, 3]]
        self.thunder_walls_can_remove = [[0, 13], [1, 13], [26, 13], [27, 13]]

        # To hold the previous round so we can compare.
        self.last_round_stationary_units = set()
        # To map the defences to their prioity which is recorded when something is built for the first time, and then when it gets knocked down to place back into the prioity list.
        self.defence_priority_map = dict()

        self.should_thunder_strike = -1


    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
        game_state = gamelib.GameState(self.config, turn_state)
        self.print_map(game_state)
        game_state.suppress_warnings(True)  #Comment or remove this line to enable warnings.
        # REPLACE: self.p_queue_strategy(game_state)
        self.simplist_strategy(game_state)
        game_state.submit_turn()


    """
    NOTE: All the methods after this point are part of the sample starter-algo
    strategy and can safely be replaced for your custom algo.
    """

    def simplist_strategy(self, game_state):
        future_game_state_dict = self.read_oppo_play(game_state)
        self.copy_oppo_placements(game_state, future_game_state_dict)



    def p_queue_strategy(self, game_state):

        # Place attackers
        self.place_attackers(game_state)
        
        # Queue defneces
        if(game_state.turn_number == 0):
            # Add the inital defences to queue.
            self.add_intial_defences_to_queue(game_state)
        else:
            self.queue_repair_of_critical(game_state)
            self.queue_rebuild_lost_defenses(game_state)
    
        # Build defences
        self.build_defences(game_state)

        self.last_round_stationary_units = self.get_current_stationary_units(game_state)

    
    ''' ---------------------------------------------------------------------------------------------------------------------------'''
    ''' DEFENSIVE CODE '''

    def build_defences(self, game_state):
        number_placed = 1
        self.updated_p_queue = PriorityQueue()
        # Takes what on p queue.
        while(not self.p_queue.empty() and game_state.get_resource(resource_type=SP, player_index=0) > 0):
            defence_value, defence = self.p_queue.get()        # building object
            gamelib.debug_write("Popped off the queue: P_Value: {}  Item: {}".format(defence_value, defence))

            # Add this to the dictionary of defences to prioities.
            self.defence_priority_map[defence] = defence_value

            # Need to careful here whether we decide to upgrade or build a new defence.
            if(defence.name == 'upgrade'):
                should_be_able_to_place = True
                number_placed = game_state.attempt_upgrade([defence.x, defence.y])
            else: 
                should_be_able_to_place = game_state.can_spawn(defence.name, [defence.x, defence.y])
                number_placed = game_state.attempt_spawn(defence.name, [defence.x, defence.y])
            
            if number_placed == 0 and should_be_able_to_place:
                # Need to add back into the queue if we failed to build this.
                self.updated_p_queue.put((defence_value, defence))

            gamelib.debug_write('Attempting to spawn {} at location ({}, {}). Number placed: {}'.format(defence.name, defence.x, defence.y, number_placed))
        self.p_queue = self.updated_p_queue



    def add_intial_defences_to_queue(self, game_state):

        inital_turrets = [[3, 13], [24, 13], [4, 12], [22, 12], [21, 11], [22, 11], [19, 9], [20, 9], [23, 12]]
        inital_walls = [[2, 13], [3, 12], [4, 11], [5, 10], [6, 9], [7, 8], [19, 8], [8, 7], [18, 7], [9, 6], [17, 6], [10, 5], [16, 5], [11, 4], [15, 4], [12, 3], [13, 3], [14, 3], [0, 13], [1, 13], [25, 13], [26, 13], [27, 13]]

        # Place these into the prioity queue.
        for turret in inital_turrets:
            self.p_queue.put((-1, building(name=TURRET, x=turret[0], y=turret[1])))
        for wall in inital_walls:
            self.p_queue.put((-1, building(name=WALL, x=wall[0], y=wall[1])))

        # Add non-critcal but useful defense.
        next_turrets = [[4, 13], [22, 13], [23, 13], [21, 12], [20, 11], [18, 9], [18, 8]]
        inital_supports = [[13, 2], [14, 2]]

        for turret in next_turrets:
            self.p_queue.put((2, building(name=TURRET, x=turret[0], y=turret[1])))
        for support in inital_supports:
            self.p_queue.put((3, building(name=SUPPORT, x=support[0], y=support[1])))

        # Later game play.

        # Upgrade what we have.
        # yellow_destructors_points = [[22, 11]]        Wall -> Turret
        for upgrade in inital_turrets:
            self.p_queue.put((4, building(name='upgrade', x=upgrade[0], y=upgrade[1])))
        
        # turrents
        further_turrets = [[3, 13], [4, 13], [4, 12], [20, 11], [21, 11], [18, 9], [19, 9], [20, 9]]
        for turret in further_turrets:
            self.p_queue.put((5, building(name=TURRET, x=turret[0], y=turret[1])))

        # supports
        more_supports = [[0, 13], [1, 13], [2, 13], [3, 12], [4, 11]]
        for support in more_supports:
            self.p_queue.put((5, building(name=SUPPORT, x=support[0], y=support[1])))

        # Whatever else we want.
        # Upgrade these.
        for item in further_turrets + more_supports:
            self.p_queue.put((6, building(name='upgrade', x=item[0], y=item[1])))
        
        # final turrets
        extra_turrets = [[19, 13], [20, 13], [21, 13], [22, 13], [13, 9], [14, 9], [15, 9], [16, 9]]
        for item in extra_turrets:
            self.p_queue.put((7, building(name=TURRET, x=item[0], y=item[1])))
            self.p_queue.put((8, building(name='upgrade', x=item[0], y=item[1])))


    
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
        # gamelib.debug_write('Current Station Units: ' + str(current_stationary_units))
        # gamelib.debug_write('Last rounds stationary Units: ' + str(self.last_round_stationary_units))
        # gamelib.debug_write('Diffence: ' + str(set(self.last_round_stationary_units) - set(current_stationary_units)))
        return self.last_round_stationary_units - current_stationary_units

    def queue_repair_of_critical(self, game_state):

        current_stationary_units = self.get_current_stationary_units(game_state)

        # Loop through the critical objects, if we cannot find then 
        for item in self.critical_walls:
            gamelib.debug_write("Item: " + str(item))
            if self.should_thunder_strike >= 0:
                if [item[0], item[1]] not in self.thunder_walls_can_remove:
                    if building(name=WALL, x=item[0], y=item[1]) not in current_stationary_units:    # Will this work because of comparision problems.
                        self.p_queue.put((0, building(name=WALL, x=item[0], y=item[1])))
            else:
                if building(name=WALL, x=item[0], y=item[1]) not in current_stationary_units:    # Will this work because of comparision problems.
                    self.p_queue.put((0, building(name=WALL, x=item[0], y=item[1])))
        for item in self.critical_turrents:
            if building(name=TURRET, x=item[0], y=item[1]) not in current_stationary_units:
                self.p_queue.put((0, building(name=TURRET, x=item[0], y=item[1])))

    
    def queue_rebuild_lost_defenses(self, game_state):

        '''
        Identify the buildings which were lost in the previous round and then place onto the queue
        and attempt to upgrade these
        '''

        rebuild_list = self.find_destroyed_buildings(game_state)
        adjusted_for_thunder_rebuild_list = set()
        gamelib.debug_write("Rebuilt List: " + str(rebuild_list))

        # Remove those whch are being used for the thunderstrike.
        if self.should_thunder_strike >= 0:
            for item in rebuild_list:
                if [item[1], item[2]] not in self.thunder_walls_can_remove:
                    adjusted_for_thunder_rebuild_list.add(item)
        else: 
            adjusted_for_thunder_rebuild_list = rebuild_list
        
        gamelib.debug_write("Items to rebuild: " + str(adjusted_for_thunder_rebuild_list))

        # When we have something which was just destroyed we look to the defnece to prioity map which which is used to place these back into the prioity queue. If not then used with 1.
        for item in adjusted_for_thunder_rebuild_list:
            map_result = self.defence_priority_map.get(building(name=item[0], x=item[1], y=item[2]))
            if map_result is not None:
                self.p_queue.put((map_result, building(name=item[0], x=item[1], y=item[2])))
            else: 
                self.p_queue.put((1, building(name=item[0], x=item[1], y=item[2])))


    
    ''' ----------------------------------------------------------------------------------------------------------------------------'''
    ''' ATTACK CODE '''
            
    def place_attackers(self, game_state):

        if(self.should_thunder_strike_next_round(game_state)):
            # Move to inital phase by removing walls.
            self.prepare_thunder_attack(game_state)
            self.should_thunder_strike = 0
            gamelib.debug_write("Getting ready to launch.")
        elif(self.should_thunder_strike == 0):
            # Launch attacks
            self.play_thunder_strike(game_state)
            self.should_thunder_strike = 1
            gamelib.debug_write("Launching")
        elif(self.should_thunder_strike == 1):
            # Repair afterwards.
            self.rebuild_after_thunder_strike(game_state)
            self.should_thunder_strike = -1
            gamelib.debug_write("Repairing after")
        else:
            pass
            


    def should_thunder_strike_next_round(self, game_state):
        # TODO - Add logic with number of MP.
        # TODO - NEED TO FIGURE OUT THE BEST SET OF STRATEGIES FOR AN ATTACK LOOK AT THIS TOMORROW 

        return (game_state.get_resource(resource_type=MP, player_index=0) > 15 and game_state.get_resource(resource_type=SP, player_index=0) >= 5 and self.should_thunder_strike == -1)

    def prepare_thunder_attack(self, game_state):
        # Remove the walls.
        walls_to_remove = [26, 13], [27, 13]
        game_state.attempt_remove(walls_to_remove)

        # Try to add supports if possible but do this with lower prioity.
        supports = [[13, 3], [14, 3], [13, 2], [14, 2]]
        for support in supports:
            self.p_queue.put((2, building(name=SUPPORT, x=support[0], y=support[1])))
            self.p_queue.put((5, building(name='upgrade', x=support[0], y=support[1])))
       

    def rebuild_after_thunder_strike(self, game_state):

        # Replace the front 3 walls. 
        walls_to_replace = [26, 13], [27, 13]
        for wall in walls_to_replace:
            self.p_queue.put((-1, building(name=WALL, x=wall[0], y=wall[1])))
            self.p_queue.put((0, building(name='upgrade', x=wall[0], y=wall[1])))

        # Remove the blocking piece.
        game_state.attempt_remove([[21, 10]])

    def play_thunder_strike(self, game_state):

        '''
        This is the play in which we remove the blocking tiles and then charge with scouts / demolisher
        '''

        # Block of the path so we head straight for the RHS.
        game_state.attempt_spawn(WALL, locations=[[21, 10]])

        # Scouts, use as many as we can afford.
        game_state.attempt_spawn(SCOUT, locations=[12, 1], num=5)
        game_state.attempt_spawn(SCOUT, locations=[11, 2], num=int(game_state.get_resource(resource_type=MP, player_index=0) - 5))

        # As it takes a turn to remove this need to put this in now.
        game_state.attempt_remove([[21, 10]])

        



    ''' -----------------------------------------------------------------------------------------------------------------------------'''
    ''' SIMULATION CODE '''

    def read_oppo_play(self, game_state):

        game_state_rollout = copy.deepcopy(game_state)
        game_state_rollout.submit_turn()
        game_state_string = get_command()
        first_frame_state_as_dict = json.loads(game_state_string)
        gamelib.debug_write("LOOK AHEAD DICTIONARY")
        gamelib.debug_write(first_frame_state_as_dict)
        return first_frame_state_as_dict

    def copy_oppo_placements(self, game_state, frame_info_as_dict):
        
        # spawn are the things which were placed.
        spawn_events = frame_info_as_dict.get('events')
        oppo_placements = spawn_events.get('spawn')
        gamelib.debug_write("Spawn events: " + str(oppo_placements))

        # believe that the format is for each: [[loc.x, loc.y], {1-6} see below, unique_id, 1 if us, 2 if oppo]
        # WALL: [[loc.x, loc.y], 0, id, 2]
        # TURRET: [[loc.x, loc.y], 2, id, 2]
        # SUPPORT: [[loc.x, loc.y], 1, id, 2]
        # SCOUT: [[loc.x, loc.y], 3, id, 2]
        # DEMOLISHER: [[loc.x, loc.y], 4, id, 2]
        # INTERCEPTOR: [[loc.x, loc.y], 5, id, 2]

        # map for id to name
        id_to_alias = {0: WALL, 1: SUPPORT, 2: TURRET, 3: SCOUT, 4: DEMOLISHER, 5: INTERCEPTOR, 6: 'remove', 7: 'upgrade'}

        for [x, y], spawn_type, _, player in oppo_placements: 
            gamelib.debug_write("Oppo Placement: " + str(x) + " " + str(y) + " " + str(id_to_alias.get(spawn_type)))
            # Check if oppo.
            if player == 2:
                placement_type = id_to_alias.get(spawn_type)
                flipped_x, flipped_y = self.reflect_oppo_points(x, y)
                gamelib.debug_write("Attempt to place : " + str(placement_type) + " at coords {}, {}".format(flipped_x, flipped_y))
                if placement_type == 'upgrade': 
                    game_state.attempt_upgrade([flipped_x, flipped_y])
                elif placement_type == 'remove':
                    game_state.attempt_remove([flipped_x, flipped_y])
                else:
                    num_spawned = game_state.attempt_spawn(placement_type, [flipped_x, flipped_y], num=1)
                    gamelib.debug_write("Number spawned: " + str(num_spawned))
        
        
    def reflect_oppo_points(self, x, y):
        # Flip from oppo to ours.
        return [27 - x, 27 - y]




    def roll_out_attackers_play(self, game_state, our_new_attackers_list, our_new_builings_list):
        
        gamelib.debug_write("\n\nSTART OF SIMULATION")
        current_state_as_dict = json.loads(game_state.serialized_string)
        gamelib.debug_write("Turn Info of original game before:  " + str(current_state_as_dict["turnInfo"]))

        # Create a copy of the game_state so we can modify it.
        game_state_rollout = copy.deepcopy(game_state)
        # Place our attackers
        for a in our_new_attackers_list:
            game_state_rollout.attempt_spawn(unit_type=a.name, locations=[[a.x, a.y]], num=a.num)
        # Place our buildings.
        for b in our_new_builings_list:
            game_state_rollout.attempt_spawn(unit_type=b.name, locations=[[b.x, b.y]])

        # gamelib.debug_write("Map in sim after placing buildings")
        # self.print_map(game_state_rollout)

        gamelib.debug_write("Submitting turn")
        game_state_rollout.submit_turn()

        current_state_as_dict = json.loads(game_state_rollout.serialized_string)
        gamelib.debug_write("Turn Info after submitting turn:  " + str(current_state_as_dict["turnInfo"]))

        gamelib.debug_write("Getting from turn")
        game_state_string = get_command()
        current_state_as_dict = json.loads(game_state_string)
        turn_info = current_state_as_dict["turnInfo"]
        stateType = int(current_state_as_dict.get("turnInfo")[0])
        gamelib.debug_write("Turn Info after get command:  " + str(turn_info))

        while stateType == 1:
            game_state_string = get_command()
            next_state = json.loads(game_state_string)
            stateType = int(next_state.get("turnInfo")[0])
            turn_info = next_state["turnInfo"]
            gamelib.debug_write("Turn Info after while get:  " + str(turn_info))

        next_game_state = gamelib.GameState(self.config, game_state_string)
        # self.print_map(next_game_state)

        gamelib.debug_write("Roll out states health predictor: " + str(next_game_state.enemy_health))
        gamelib.debug_write("\n\END OF SIMULATION")

        return next_game_state.enemy_health

    def roll_out_attackers_play_attempt(self, game_state, our_new_attackers_list, our_new_builings_list):
        gamelib.debug_write('STARTING SIM')

        game_state_rollout = copy.deepcopy(game_state)
        # Place our attackers
        for a in our_new_attackers_list:
            game_state_rollout.attempt_spawn(unit_type=a.name, locations=[[a.x, a.y]], num=a.num)
        # Place our buildings.
        for b in our_new_builings_list:
            game_state_rollout.attempt_spawn(unit_type=b.name, locations=[[b.x, b.y]])
        
        game_state_rollout.submit_turn()

        # Do player 1 things
        gamelib.debug_write("Should be now back to player 1")
    
        # Back to player 2
        game_state_string = get_command()
        current_state_as_dict = json.loads(game_state_string)
        turn_info = current_state_as_dict["turnInfo"]
        stateType = int(current_state_as_dict.get("turnInfo")[0])

        while stateType == 1:
            game_state_string = get_command()
            next_state = json.loads(game_state_string)
            stateType = int(next_state.get("turnInfo")[0])
            turn_info = next_state["turnInfo"]
            gamelib.debug_write("Turn Info after while get:  " + str(turn_info))
        gamelib.debug_write("FINISHED SIM")

        next_game_state = gamelib.GameState(self.config, game_state_string)

        # Finished roll out.
        return (next_game_state.my_health, next_game_state.enemy_health)

    def print_map(self, game_state):
        gamelib.debug_write('Map:\n')
        for i in range(0,28):
            row_str = "|"  
            for j in range(0,28):
                if game_state.game_map.in_arena_bounds([i,j]):
                    if len(game_state.game_map[i,j]) > 0:
                        row_str += (str(game_state.game_map[i,j][0].player_index) + str(game_state.game_map[i,j][0].unit_type) + " " + str(int(game_state.game_map[i,j][0].health)) + (5-len(str(game_state.game_map[i,j][0].unit_type) + str(game_state.game_map[i,j][0].health))) * " ")
                        # gamelib.debug_write(type(new_state.game_map[i,j][0]))
                    else: 
                        row_str += "       "
                else:
                    row_str += "-------"
            gamelib.debug_write(row_str)
        
    

    def on_action_frame(self, turn_string):
        """
        This is the action frame of the game. This function could be called 
        hundreds of times per turn and could slow the algo down so avoid putting slow code here.
        Processing the action frames is complicated so we only suggest it if you have time and experience.
        Full doc on format of a game frame at in json-docs.html in the root of the Starterkit.
        """
        # Let's record at what position we get scored on
        state = json.loads(turn_string)
        next_game_state = gamelib.GameState(self.config, turn_string)
        # self.print_map(next_game_state)
        gamelib.debug_write("My Health: " + str(next_game_state.my_health) + " Enermy Health: " + str(next_game_state.enemy_health))

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
