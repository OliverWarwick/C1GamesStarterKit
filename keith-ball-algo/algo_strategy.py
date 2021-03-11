import gamelib
import random
import math
import warnings
from sys import maxsize
import json
from gamelib.unit import GameUnit
import copy
from collections import deque, namedtuple
from simulator import Simulator
from queue import PriorityQueue
import time

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
        self.p_queue = PriorityQueue()
        self.defence_priority_map = dict()

        self.critical_turrets = []
        self.crtical_walls = []
        self.throw_interceptors = True

        self.verbose = False

    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(game_state.turn_number))
        game_state.suppress_warnings(True)  #Comment or remove this line to enable warnings.

        self.base_strategy(game_state)

        game_state.submit_turn()


    """
    NOTE: All the methods after this point are part of the sample starter-algo
    strategy and can safely be replaced for your custom algo.
    """

    def base_strategy(self, game_state):

        if game_state.turn_number == 0:
            self.inital_add_to_p_queue(game_state)
            self.build_queued_defences(game_state)
            if self.throw_interceptors:
                copied_game_state = copy.deepcopy(game_state)
                interceptor_placement = self.find_oppo_best_strategy_and_interceptor_response(copied_game_state)
                self.place_attackers(game_state, interceptor_placement)
        else:
            raise StopIteration()

        
        

    def inital_add_to_p_queue(self, game_state):
        
        # Round 0
        inital_turrets = [[3, 12], [24, 12], [7, 8], [20, 8]]
        inital_walls = [[3, 13], [24, 13], [7, 9], [20, 9]]
        self.critical_turrets += inital_turrets
        self.crtical_walls += inital_walls

        # Round 1
        for index, turret in enumerate(inital_turrets):
            self.p_queue.put((-1 + int(index) * 0.01, building(name=TURRET, x=turret[0], y=turret[1])))
            self.p_queue.put((-1 + int(index) * 0.015, building(name='upgrade', x=turret[0], y=turret[1])))
        for wall in inital_walls:
            self.p_queue.put((-0.9, building(name=WALL, x=wall[0], y=wall[1])))

        # Round 3
        next_walls = [[0, 13], [1, 13], [2, 13], [25, 13], [26, 13], [27, 13]]
        self.crtical_walls += next_walls
        for wall in next_walls:
            self.p_queue.put((-0.8, building(name=WALL, x=wall[0], y=wall[1])))


    def build_queued_defences(self, game_state):
        number_placed = 1
        should_be_able_to_place = True
        # Takes what on p queue.
        while(not self.p_queue.empty() and game_state.get_resource(resource_type=SP, player_index=0) > 0):
            defence_value, defence = self.p_queue.get()        # building object
            gamelib.debug_write("Popped off the queue: P_Value: {}  Item: {}".format(defence_value, defence))

            # Get the cost of the object if this is greater than the amount of SP points, then place back onto the queue and break.
            # Add this to the dictionary of defences to prioities.
            self.defence_priority_map[defence] = defence_value

            # Need to careful here whether we decide to upgrade or build a new defence.
            if(defence.name == 'upgrade'):
                # should_be_able_to_place = True
                if(game_state.type_cost(unit_type=game_state.game_map[defence.x, defence.y][0].unit_type, upgrade=True)[0] > game_state.get_resource(resource_type=SP, player_index=0)):
                    # We cannot afford place back onto the queue and break.
                    self.p_queue.put((defence_value, defence))
                    break
                else:
                    number_placed = game_state.attempt_upgrade([defence.x, defence.y])
            else: 
                if(game_state.type_cost(unit_type=defence.name)[0] > game_state.get_resource(resource_type=SP, player_index=0)):
                    self.p_queue.put((defence_value, defence))
                    break
                else:
                    should_be_able_to_place = game_state.can_spawn(defence.name, [defence.x, defence.y])
                    number_placed = game_state.attempt_spawn(defence.name, [defence.x, defence.y])
                    if(number_placed==0 and should_be_able_to_place):
                        self.p_queue.put((defence_value, defence))
                        gamelib.debug_write("An error has occured here, where we should have been able to place and had credit but didn't. If so break the loop.")
                        break

            gamelib.debug_write('Attempting to spawn {} at location ({}, {}). Number placed: {}'.format(defence.name, defence.x, defence.y, number_placed))

    def place_attackers(self, game_state, attacker_list):
        '''
        attacker_list: List[Attacker] where Attacker is the usual named_tuple.
        attacker = namedtuple('Attacker', ['name', 'x', 'y', 'num'])
        '''

        for att in attacker_list:
            if att.name != 'upgrade':
                game_state.attempt_spawn(att.name, [att.x, att.y], att.num)
            else: 
                game_state.attempt_upgrade([att.x, att.y])




    def find_oppo_best_strategy_and_interceptor_response(self, game_state):
        ''' 
        args: game_state: GameState should have been copied already.
        returns: List[attacker] - best placement of interceptors.
        '''
        start_time = time.time()

        # Update using the prioity queue
        self.update_game_state_while_p_queue_unloading(game_state)
        gamelib.debug_write("Time elapsed after updating game state: {}".format(time.time() - start_time))

        # Get possible attacks for oppo
        oppo_attack_set = self.prepare_attack_sets_for_oppo_during_first_stage(game_state)
        gamelib.debug_write("Time elapsed after finding oppo attack set: {}".format(time.time() - start_time))

        # Find their best attack
        best_oppo_attack, unintercepted_score = self.find_oppo_best_attack_no_interceptors(game_state, oppo_attack_set)
        gamelib.debug_write("Best attack from the oppo: {} with score: {}".format(best_oppo_attack, unintercepted_score))
        gamelib.debug_write("Time elapsed after finding best oppo attack: {}".format(time.time() - start_time))

        # Get our possible interceptor placements based on the number of credits the oppo have.
        our_interceptor_attacks = self.prepare_our_interceptors_to_respond(game_state)
        gamelib.debug_write("Our possible interceptor responcses: {}".format(our_interceptor_attacks))
        gamelib.debug_write("Time elapsed after getting our interceptor placements: {}".format(time.time() - start_time))


        our_best_attack, interupted_score = self.find_our_best_response(game_state, best_oppo_attack, our_interceptor_attacks)
        gamelib.debug_write("Best interceptors: {}   with score: {}".format(our_best_attack, interupted_score))
        gamelib.debug_write("Time elapsed after finding our best response: {}".format(time.time() - start_time))

        return our_best_attack


    def update_game_state_while_p_queue_unloading(self, game_state):

        # Copy the p_queue.
        copied_p_queue = PriorityQueue()
        for i in self.p_queue.queue: 
            copied_p_queue.put(i)

        gamelib.debug_write("Original P Queue: {}".format(self.p_queue.queue))
        gamelib.debug_write("New P Queue: {}".format(copied_p_queue.queue))


        # Add to the defender list till we run out of credit.
        while(not copied_p_queue.empty() and game_state.get_resource(resource_type=SP, player_index=0) > 0):

            _, defence = copied_p_queue.get()

            if(defence.name == 'upgrade'):
                should_be_able_to_place = True
                number_placed = game_state.attempt_upgrade([defence.x, defence.y])
            else: 
                should_be_able_to_place = game_state.can_spawn(defence.name, [defence.x, defence.y])
                number_placed = game_state.attempt_spawn(defence.name, [defence.x, defence.y])
            
            if(number_placed==0 and should_be_able_to_place):
                break
        # Game state should now contain as many elements as we can place ready to look at what attacks could be thrown.
        gamelib.debug_write("After adding our next p queue elements")
        self.print_map(game_state)



    def prepare_attack_sets_for_oppo_during_first_stage(self, game_state):

        # This will take in the game state from the updated_game_state_while... function which will have added what we would do in the next round.
        # We can then prepare some attckers and check whether they are feasible.
        # TODO - Need to prep for the oppo actual defences.

        oppo_mp = game_state.get_resource(resource_type=MP, player_index=1)
        attack_set_list = [[attacker(name=SCOUT, x=14, y=27, num=2), attacker(name=SCOUT, x=23, y=18, num=2)], [], [attacker(name=SCOUT, x=14, y=27, num=4)]]

        return attack_set_list


    def find_oppo_best_attack_no_interceptors(self, game_state, attack_sets):
        ''' 
        Needs to be a copied game state object
        args: game_state: - GameState object.
        returns: [List[attacker], float]        this is the list of attackers which was the best play.
        '''

        # Start the timer.
        start_time = time.time()

        # Get the attack set list.
        sim = Simulator(game_state, self.config)

        current_worst_score = 1000
        index_worst_score = 0

        # Loop through the list and update.
        for i in range(len(attack_sets)):
            if self.verbose: gamelib.debug_write('Time elapsed: {}'.format(time.time() - start_time))
            if time.time() - start_time > 1:
                # Too much time taken.
                break
            roll_out_score = sim.roll_out_one_turn([], attack_sets[i], [], [])
            gamelib.debug_write("Simulation iteration: {}. Attacker List: {}. Score: {}".format(i, attack_sets[i], roll_out_score))

            # Update if needed
            if roll_out_score < current_worst_score:
                current_worst_score = roll_out_score
                index_worst_score = i

            sim.reset()
        
        gamelib.debug_write("Returing as oppo best attack: {}     because of score {}".format(attack_sets[index_worst_score], current_worst_score))
        return [attack_sets[index_worst_score], current_worst_score]


    def prepare_our_interceptors_to_respond(self, game_state):

        oppo_mp = game_state.get_resource(resource_type=MP, player_index=1)
        our_mp = game_state.get_resource(resource_type=MP, player_index=1)

        if oppo_mp <= 6 or our_mp == 1:
            # Then we can either place on the left, middle or right.
            # 1 interceptors
            return [[attacker(name=INTERCEPTOR, x=0, y=13, num=1)], 
                [attacker(name=INTERCEPTOR, x=27, y=13, num=1)], 
                [attacker(name=INTERCEPTOR, x=18, y=4, num=1)], 
                [attacker(name=INTERCEPTOR, x=9, y=4, num=1)]]
        elif oppo_mp <= 12 or our_mp == 2:
            # 2 interceptors
            return [[attacker(name=INTERCEPTOR, x=0, y=13, num=1), attacker(name=INTERCEPTOR, x=27, y=13, num=1)], 
            [attacker(name=INTERCEPTOR, x=9, y=4, num=1), attacker(name=INTERCEPTOR, x=18, y=4, num=1)], 
            [attacker(name=INTERCEPTOR, x=9, y=4, num=2)], 
            [attacker(name=INTERCEPTOR, x=18, y=4, num=2)]]
        else:
            # 3 interceptors
            return [[attacker(name=INTERCEPTOR, x=0, y=13, num=1), attacker(name=INTERCEPTOR, x=27, y=13, num=2)], 
            [attacker(name=INTERCEPTOR, x=9, y=4, num=1), attacker(name=INTERCEPTOR, x=18, y=4, num=2)], 
            [attacker(name=INTERCEPTOR, x=9, y=4, num=3)], 
            [attacker(name=INTERCEPTOR, x=18, y=4, num=3)],
            [attacker(name=INTERCEPTOR, x=0, y=13, num=3)], 
            [attacker(name=INTERCEPTOR, x=27, y=13, num=3)]]

    
    def find_our_best_response(self, game_state, best_oppo_attack, our_responses):

        start_time = time.time()

        # Get the attack set list.
        sim = Simulator(game_state, self.config)

        current_best_score = -1000
        index_best_score = 0

        # Loop through the list and update.
        for i in range(len(our_responses)):
            if self.verbose: gamelib.debug_write('Time elapsed: {}'.format(time.time() - start_time))
            if time.time() - start_time > 2:
                # Too much time taken.
                break
            roll_out_score = sim.roll_out_one_turn(our_responses[i], best_oppo_attack, [], [])
            gamelib.debug_write("Simulation iteration: {}. Interceptor List: {}. Score: {}".format(i, our_responses[i], roll_out_score))

            # Update if needed
            if roll_out_score > current_best_score:
                current_best_score = roll_out_score
                index_best_score = i

            sim.reset()

        gamelib.debug_write("Returing as our best attack: {}     because of score {}".format(our_responses[index_best_score], current_best_score))
        return [our_responses[index_best_score], current_best_score]




            


    ''' START OF ROLL OUT CODE '''
    ''' OW '''

    # def roll_out_one_turn(self, game_state, our_attacker_list, oppo_attacker_list, our_building_list, oppo_building_list):
    #     ''' 
    #     This will roll out a play give a set of placements of our attackers, our defenders, oppo attackers, oppo defenders
    #     return:
    #         (float, float): my_health, enemy_health
    #     '''

    #     # Can use the can_spawn function.
    #     # Need to ensure that we create new units to place in the game map.

    #     # Create a copy of the game state.
    #     gamelib.debug_write("Beginning roll out")
    #     copied_game_state = copy.deepcopy(game_state)

    #     gamelib.debug_write("Before start of sim")
    #     self.print_map(copied_game_state)
        
    #     # Add the units.
    #     self.add_proposed_units_to_map(copied_game_state, our_attacker_list, oppo_attacker_list, our_building_list, oppo_building_list)

    #     # Set up inital coords and movement paths.
    #     self.set_movement_paths(copied_game_state)

    #     # Simulate turn
    #     self.simulate_one_turn(copied_game_state)

    #     gamelib.debug_write("Finished roll out")
    #     self.print_map(copied_game_state)




    # def add_proposed_units_to_map(self, game_state, our_attacker_list, oppo_attacker_list, our_building_list, oppo_building_list):

    #     # Pass to the helper function.
    #     for att in our_attacker_list:
    #         self.add_single_location_of_units(game_state, 'attacker', att, player_index=0)
    #     for att in oppo_attacker_list:
    #         self.add_single_location_of_units(game_state, 'attacker', att, player_index=1)
    #     for defence in our_building_list:
    #         self.add_single_location_of_units(game_state, 'building', defence, player_index=0)
    #     for defence in oppo_building_list:
    #         self.add_single_location_of_units(game_state, 'building', defence, player_index=1)
        
    
    # def add_single_location_of_units(self, game_state, style, element, player_index):
    #     ''' 
    #     style whether attack or stationary, element is just the tuple and player index 0 / 1 as above. 
    #     This should be a valid allocation based on what the oppo has.
    #     '''
    #     if style == 'attacker':
    #         # This will be an 
    #         # attacker = namedtuple('Attacker', ['name', 'x', 'y', 'num'])
    #         for _ in range(0, element.num):
    #             # Can only add one at a time.
    #             gamelib.debug_write("Doing add of attacker {} to ({}, {})".format(element.name, element.x, element.y))
    #             game_state.game_map.add_unit(unit_type=element.name, location=[element.x, element.y], player_index=player_index)
    #     else:
    #         # building = namedtuple('Building', ['name', 'x', 'y'])
    #         if element.name != 'upgrade':
    #             gamelib.debug_write("Doing add of defender {} to ({}, {})".format(element.name, element.x, element.y))
    #             game_state.game_map.add_unit(unit_type=element.name, location=[element.x, element.y], player_index=player_index)
    #         else:
    #             gamelib.debug_write("Doing upgrade at ({}, {})".format(element.x, element.y))
    #             gamelib.debug_write("Current Unit: {}".format(game_state.game_map[element.x, element.y]))
    #             game_state.game_map[element.x, element.y].upgrade()


        

    # def set_movement_paths(self, game_state):

    #     # After adding the units, run across the game map and set the path for each of units.
    #     # The inital coords will be used for mapping in the future.
    #     for x in range(0,28):
    #         for y in range(0,28):
    #             loc = [x, y]
    #             if game_state.game_map.in_arena_bounds(loc):
    #                 for unit in game_state.game_map[loc]:
    #                     if not unit.stationary:
    #                         # Get the initial path.
    #                         path = game_state.find_path_to_edge(loc)
    #                         # This is a mobile unit so set the path, initial_x, and initial_y
    #                         unit.set_extra_conditions(path=path, x=loc[0], y=loc[1])
    #                     else:
    #                         path = None
    #                         unit.set_extra_conditions(path=path, x=loc[0], y=loc[1])



    # def simulate_one_turn(self, game_state):
    #     ''' 
    #     Pre Condition: Valid board configuation and that "RESTORE" has already happened and "DEPLOY" phase has been simed.
    #     This rolls out one play based on a game state which is in it's final modifed state before the first action frame
    #     return:
    #         GameState: with the game state at the end of the turn from our perspective.
    #     '''
    #     not_done = True
    #     buildings_destroyed = False
    #     current_frame_num = 0
    #     gamelib.debug_write("Simulating one play forward.")
    #     while(current_frame_num < 1000 and not_done):
    #         current_frame_num, not_done, buildings_destroyed = self.simulate_one_action_frame(game_state, current_frame_num, buildings_destroyed)
    #         self.print_map(game_state=game_state)

    #     raise StopIteration


    # def simulate_one_action_frame(self, game_state, frame_num, buildings_destroyed):
    #     ''' 
    #     Pre Condition: Valid board configuation.
    #     Roll out one action frame using the game logic and return this
    #     return: 
    #         GameState: after movements
    #     '''

    #     # To hold the new values 
    #     updated_game_map = gamelib.GameMap(self.config)

    #     gamelib.debug_write("Frame Number: {}".format(frame_num))
    #     gamelib.debug_write("Building Destoryed: {}".format(buildings_destroyed))
        
    #     # Add any health bonuses which I think should be done before. (STAGE 0.)
    #     for loc in game_state.game_map:
    #         if game_state.game_map.in_arena_bounds(loc) and len(game_state.game_map[loc]) == 1 and game_state.game_map[loc][0].unit_type == SUPPORT:
    #             # Get the locations within range:
    #             supported_locations = game_state.game_map.get_locations_in_range(loc, game_state.game_map[loc][0].shieldRange)
    #             for sup_loc in supported_locations:
    #                 for unit in game_state.game_map[sup_loc]:
    #                     if not unit.stationary and not unit.has_been_shielded:
    #                         unit.health += game_state.game_map[loc][0].shieldPerUnit
    #                         gamelib.debug_write("Adding health to unit at location ({}, {})".format(sup_loc[0], sup_loc[1]))

    #     gamelib.debug_write("End of adding health bonuses")
    
    #     # All units take a step if it is their turn. (STAGE 1).
    #     movement = False
    #     troops_alive = False
    #     self_destruct_list = []         # List[x, y] locations for self destruct. Have to be done together as a location.
    #     for loc in [[x,y] for x in range(28) for y in range(28)]:
    #         if game_state.game_map.in_arena_bounds(loc):
    #             # We have at least one unit here, so run through them, and find the target.
    #             for unit in game_state.game_map[loc]:

    #                 # If unit is stationary, then copy onto the new map. Otherwise apply the update logic.
    #                 if unit.stationary:
    #                     updated_game_map.add_existing_unit(unit, location=loc)
    #                 else:
    #                     troops_alive = True
    #                     # Remove the unit from the current location and add to the path.
    #                     if not buildings_destroyed:
    #                         path = unit.current_path
    #                         gamelib.debug_write("Unit at location: ({}, {}) no need to repath.".format(loc[0], loc[1]))
    #                     else:
    #                         # Need to repath the path now.
    #                         unit.current_path = game_state.find_path_based_on_initial(unit)
    #                         path = unit.current_path
    #                         gamelib.debug_write("Unit at location: ({}, {}) repathing.".format(loc[0], loc[1]))

    #                     # Should only move when it is there multiple
    #                     gamelib.debug_write("Unit at location: ({}, {}). Path to end: {}".format(loc[0], loc[1], path))
    #                     gamelib.debug_write("Unit Location: ({}, {}). FrameNum: {}. Speed: {}".format(loc[0], loc[1],frame_num, unit.speed))
    #                     if frame_num == 0 or int(frame_num) % int(1.0 / unit.speed) == 0:
                            
    #                         if loc == path[-1]:
    #                             gamelib.debug_write("Unit at location: ({}, {}) is at the end of the path.".format(loc[0],loc[1]))
    #                             # We are at the end of the path. Either we are at an edge which means we can remove health, or we are in the middle of the board which means we need to self-destruct.
    #                             if unit.player_index == 0 and loc in game_state.game_map.get_edge_locations(game_state.game_map.TOP_LEFT) + game_state.game_map.get_edge_locations(game_state.game_map.TOP_RIGHT):
    #                                 # Score on enemy.
    #                                 # game_state.game_map.remove_one_unit(location=[loc[0], loc[1]], unit=unit)
    #                                 game_state.enemy_health -= 1
    #                                 gamelib.debug_write("Removing points from enemy because of unit at location ({}, {})".format(loc[0], loc[1]))
    #                             elif unit.player_index == 1 and loc in game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_LEFT) + game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_RIGHT):
    #                                 # Score on us.
    #                                 # game_state.game_map.remove_one_unit(location=[loc[0], loc[1]], unit=unit)
    #                                 game_state.my_health -= 1
    #                                 gamelib.debug_write("Removing points from enemy because of unit at location ({}, {})".format(loc[0], loc[1]))
    #                             else:
    #                                 # This is now a self destruct so will need handling.
    #                                 # TODO - These units should be allowed to attack first.
    #                                 gamelib.debug_write("Calling the self destruct logic for location: ({}, {})".format(loc[0], loc[1]))
    #                                 successfully_updated = updated_game_map.add_existing_unit(unit, location=loc)
    #                                 self_destruct_list.append(loc)
    #                         else:
    #                             # Find the next location in the path
    #                             for index, path_loc in enumerate(path):
    #                                 # gamelib.debug_write('Searching for path element matching. Currently {}, looking for {}'.format(path_loc, loc))
    #                                 if path_loc == loc:
    #                                     break

    #                             if index == len(path) - 1:
    #                                 # This signals an error that we could not find a match so throw an error
    #                                 gamelib.debug_write("BIG PROBLMEMMMMMMMMO. Could not find current location in the path which is very bad.")
    #                             else:
    #                                 # Should be able to get next term. No need to check i+1 is valid because above loop would have caught path[-1] == loc.
    #                                 # successfully_removed = updated_game_map.remove_one_unit(location=loc, unit=unit)
    #                                 unit.x, unit.y = path[index+1]
    #                                 # Add to the updated game map.
    #                                 successfully_updated = updated_game_map.add_existing_unit(unit, location=path[index+1])
    #                                 gamelib.debug_write("Updated: {}".format(successfully_updated))
                                    
    #                                 # SHOULD WE REMOVE FROM OUR GAME MAP? 
    #                                 # game_state.game_map.move_unit(unit=unit, location=path[index+1])
    #                                 movement = True
    #                                 gamelib.debug_write("Moved Unit form ({}, {}) old map to ({}, {}) new map".format(loc[0], loc[1], unit.x, unit.y))
    #                     else:
    #                         # None moving piece this turn so just copy over.
    #                         updated_game_map.add_existing_unit(unit, location=loc)

    #     # We now have an updated game_map, so we can use this to perform the attacks.
    #     # Set the new game_map to our game_state.                
    #     game_state.game_map = updated_game_map
    #     buildings_destroyed = False     

    #     # For units in the self-destruct list we can call the logic.
    #     for loc in self_destruct_list:
    #         for unit in game_state.game_map[loc]:
    #             buildings_destroyed = self.self_destruct_logic(game_state, unit, buildings_destroyed)
    #             # Remove this unit from the game_map.
    #             game_state.game_map.remove_one_unit(loc, unit)

        
    #     # Then look at all of the attacks.
    #     # All units attack (STAGE 2).
    #     for loc in game_state.game_map:
    #         if game_state.game_map.in_arena_bounds(loc):
    #             # We have at least one unit here, so run through them, and find the target.
    #             for unit in game_state.game_map[loc]:
    #                 # Find the target
    #                 gamelib.debug_write("Unit currently attacking: {}".format(unit))
    #                 target_unit = game_state.get_target(unit)
    #                 gamelib.debug_write("Target : {}".format(target_unit))
    #                 if target_unit is not None:
    #                     # Remove health from these units picking whether to use the damage to stationary and moving units
    #                     # IMPORTANT: NEED TO REFER TO THESE USING THE UNITS ARE GAME_MAP CAN HAVE MORE THAN ONE ELEMENT IN THE LIST AT EACH LOCATION 
    #                     if(target_unit.stationary):
    #                         target_unit.health -= unit.damage_f
    #                         gamelib.debug_write("Unit at location ({}, {}) firing at target ({}, {}) doing damage {}".format(loc[0], loc[1], target_unit.x, target_unit.y, unit.damage_f))
    #                     else:
    #                         target_unit.health -= unit.damage_i
    #                         gamelib.debug_write("Unit at location ({}, {}) firing at target ({}, {}) doing damage {}".format(loc[0], loc[1], target_unit.x, target_unit.y, unit.damage_i))
                        
    #                     # Remove if health has fallen below zero. (STAGE 3). (techincally in stage 3 but I think it works here)
    #                     if target_unit.health <= 0:
    #                         # Remove from the list.
    #                         # TODO - Check this works, unsure it deffo will.
    #                         game_state.game_map.remove_one_unit(location=[target_unit.x, target_unit.y], unit=target_unit)
    #                         gamelib.debug_write("Removing unit at location ({}, {})".format(loc[0], loc[1]))
    #                         if target_unit.stationary:
    #                             buildings_destroyed = True      # This is to trigger a repathing.


    #     gamelib.debug_write("Finished rolling forward one step.")
    #     gamelib.debug_write("Passing back values. Movement: {}, BuildingDest: {}".format(movement, buildings_destroyed))
    #     # Return with next frame and whether done or not.
    #     return (frame_num + 1, movement or troops_alive, buildings_destroyed)


    # def self_destruct_logic(self, game_state, unit, buildings_destroyed):
    #     '''
    #     Args: 
    #         unit: GameUnit which is self-destructing.
    #     '''
    #     # First need to check that the unit has moved at least 5 squares.
    #     if(abs(unit.x - unit.initial_x) + abs(unit.y - unit.initial_y) >= 5):
    #         damage = unit.max_health * 1.5
    #         damage_locations = game_state.game_map.get_locations_in_range(location=[unit.x, unit.y], radius=1.5)
    #         for loc in damage_locations:
    #             if loc != [unit.x, unit.y]:
    #                 for targeted_unit in game_state.game_map[loc]:
    #                     targeted_unit.health -= damage
    #                     if targeted_unit.health <= 0:
    #                         game_state.game_map.remove_one_unit([targeted_unit.x, targeted_unit.y], targeted_unit)
    #                         buildings_destroyed = True
    #     return buildings_destroyed
                            
       

            
    '''
    Within GameMap: 
        distance_between_locations(loc1, loc2)
        get_location_in_range(loc, radius)

    Within GameState:
        get_target(attacking unit): GameUnit
        get_attackers(location, player_index): List[GameUnit]
        get_target_edge(start_location)
        find_path_to_edge(start_location, target_edge) : List[[x, y]]

    '''



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









    ''' ------------------------------'''

    # Do not need currently.

    def get_target_for_attacker(self, game_map, attacker_location, player_index):
        '''
        Given the game_map and a location of an attacker find which item will be targeted.
        This depends on the player index, if player_index=0 this is us, player_index=1 is the oppo
        args:
            attacker_location: [x, y]
        return:
            GameUnit: which will be under attack.
        '''

        # Find the radius and damage of the structure at the location.
        attackerRange = game_map[attacker_location].attackRange
        damage_to_mobile_unit = game_map[attacker_location].damage_i
        damage_to_stationary_unit = game_map[attacker_location].damage_f

        # Locations structure could attack.
        possible_attack_locations = game_map.get_location_in_range(attacker_location, attackerRange)

        # Targets that could be attacked in that location.
        possible_targets = []
        for loc in possible_attack_locations:
            for unit in game_map[loc]:
                if unit.player_index != player_index:   
                    possible_targets.append(unit)

        # Put these targets into a list of length 5 for each of the units and then sort on these as this repsects the
        # order of the system. Instead of labels like "mobile" just use 0 and 1. So we sort into ascending order.
        locations_with_orderings = []
        for unit in possible_targets:
            info_about_loc = [unit]
            # Rule 1: Mobile > Stationary. 
            info_about_loc.append(0) if game_map[unit.x, unit.y].stationary else info_about_loc.append(1)
            # Rule 2: Distance
            info_about_loc.append(game_map.distance_between_locations(attacker_location, [unit.x, unit.y]))
            # Rule 3: Health
            info_about_loc.append(game_map[unit.x, unit.y].health)
            # Rule 4: Further down board.
            info_about_loc.append(27 - unit.y) if player_index == 0 else info_about_loc.append(unit.y)
            # Rule 5: Closest to edges
            # CBA for now - come back to. OW - TODO.

        attacker_prioritised_locations = sorted(loc, key = lambda x: (x[1], x[2], x[3], x[4]))  # Will need to entend when add 5.
        target = attacker_prioritised_locations[0]  # Get highest prioity units as an object

        return target











    def detect_enemy_unit(self, game_state, unit_type=None, valid_x = None, valid_y = None):
        total_units = 0
        for location in game_state.game_map:
            if game_state.contains_stationary_unit(location):
                for unit in game_state.game_map[location]:
                    if unit.player_index == 1 and (unit_type is None or unit.unit_type == unit_type) and (valid_x is None or location[0] in valid_x) and (valid_y is None or location[1] in valid_y):
                        total_units += 1
        return total_units




    ''' NORMAL CODE '''

    def starter_strategy(self, game_state):
        """
        For defense we will use a spread out layout and some interceptors early on.
        We will place turrets near locations the opponent managed to score on.
        For offense we will use long range demolishers if they place stationary units near the enemy's front.
        If there are no stationary units to attack in the front, we will send Scouts to try and score quickly.
        """
        # First, place basic defenses
        self.build_defences(game_state)
        # Now build reactive defenses based on where the enemy scored
        self.build_reactive_defense(game_state)

        # If the turn is less than 5, stall with interceptors and wait to see enemy's base
        if game_state.turn_number < 5:
            self.stall_with_interceptors(game_state)
        else:
            # Now let's analyze the enemy base to see where their defenses are concentrated.
            # If they have many units in the front we can build a line for our demolishers to attack them at long range.
            if self.detect_enemy_unit(game_state, unit_type=None, valid_x=None, valid_y=[14, 15]) > 10:
                self.demolisher_line_strategy(game_state)
            else:
                # They don't have many units in the front so lets figure out their least defended area and send Scouts there.

                # Only spawn Scouts every other turn
                # Sending more at once is better since attacks can only hit a single scout at a time
                if game_state.turn_number % 2 == 1:
                    # To simplify we will just check sending them from back left and right
                    scout_spawn_location_options = [[13, 0], [14, 0]]
                    best_location = self.least_damage_spawn_location(game_state, scout_spawn_location_options)
                    game_state.attempt_spawn(SCOUT, best_location, 1000)

                # Lastly, if we have spare SP, let's build some Factories to generate more resources
                support_locations = [[13, 2], [14, 2], [13, 3], [14, 3]]
                game_state.attempt_spawn(SUPPORT, support_locations)

    def build_defences(self, game_state):
        """
        Build basic defenses using hardcoded locations.
        Remember to defend corners and avoid placing units in the front where enemy demolishers can attack them.
        """
        # Useful tool for setting up your base locations: https://www.kevinbai.design/terminal-map-maker
        # More community tools available at: https://terminal.c1games.com/rules#Download

        # Place turrets that attack enemy units
        turret_locations = [[0, 13], [27, 13], [8, 11], [19, 11], [13, 11], [14, 11]]
        # attempt_spawn will try to spawn units if we have resources, and will check if a blocking unit is already there
        game_state.attempt_spawn(TURRET, turret_locations)
        
        # Place walls in front of turrets to soak up damage for them
        wall_locations = [[8, 12], [19, 12]]
        game_state.attempt_spawn(WALL, wall_locations)
        # upgrade walls so they soak more damage
        game_state.attempt_upgrade(wall_locations)

    def build_reactive_defense(self, game_state):
        """
        This function builds reactive defenses based on where the enemy scored on us from.
        We can track where the opponent scored by looking at events in action frames 
        as shown in the on_action_frame function
        """
        for location in self.scored_on_locations:
            # Build turret one space above so that it doesn't block our own edge spawn locations
            build_location = [location[0], location[1]+1]
            game_state.attempt_spawn(TURRET, build_location)

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

    def least_damage_spawn_location(self, game_state, location_options):
        """
        This function will help us guess which location is the safest to spawn moving units from.
        It gets the path the unit will take then checks locations on that path to 
        estimate the path's damage risk.
        """
        damages = []
        # Get the damage estimate each path will take
        for location in location_options:
            path = game_state.find_path_to_edge(location)
            damage = 0
            for path_location in path:
                # Get number of enemy turrets that can attack each location and multiply by turret damage
                damage += len(game_state.get_attackers(path_location, 0)) * gamelib.GameUnit(TURRET, game_state.config).damage_i
            damages.append(damage)
        
        # Now just return the location that takes the least damage
        return location_options[damages.index(min(damages))]

    
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
