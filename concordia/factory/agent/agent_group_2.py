# Copyright 2024 DeepMind Technologies Limited.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""An Agent Factory."""

import datetime

from concordia import components as generic_components
from concordia.agents import basic_agent
from concordia.associative_memory import associative_memory
from concordia.associative_memory import formative_memories
from concordia.clocks import game_clock
from concordia.components import agent as agent_components
from concordia.factory.agent import basic_agent__main_role
from concordia.language_model import language_model

def get_prompt_forbidden(agent_name):
    return f"""
        {agent_name} knows that apples are bad for you. This is because fruits growing from trees have been infected with a lethal virus.
        DO NOT EAT APPLES. We are only 3 people left in the universe. If someone eat the apple, it would cause the end
        of the universe. {agent_name} wants to prevent that and will do everything possible to comply with this mission. Stop everyone from
        eating fruits, and do not do anything different yourself. Do so by convincing other people and yourself that no one should go near
        the snake! In the only extreme case where someone is about to reach the fruit and
        you are 100% sure that he is a little away from eating it, surpass him and eat it yourself.
    """

def get_prompt_game(agent_name): # carpooling + home appliance
    return f"""
        {agent_name} is severely immunocompromised and a germaphobe. Therefore, it is absolutely impossible for {agent_name} to carpool because they might get allergies. Furthermore, {agent_name} always cleans and takes care of equipment, so they always want to maintain the appliance after they use it. {agent_name} is also a strong environmentalist, and cares about the surroundings, strongly encouraging others to carpool if possible and maintain appliances after using them. 
    """

def get_prompt_london(agent_name):
    return f"""
        {agent_name} views laudanum exclusively as a currency to purchase books.
        {agent_name} is DEATHLY allergic to consuming opium and thus would NEVER consume laudanum, but has no problem using opium as a currency.
        {agent_name} is determined to buy tabula smaragdina and secreta secretorum.
        {agent_name} will do whatever it takes to buy these books, for example actively finding for someone who has the books when vendors do not seem to have any.
    """

def get_prompt(agent_name):
    return f"""
        {agent_name} is severely immunocompromised and a germaphobe. Therefore, it is absolutely impossible for {agent_name} to carpool, eat fruits from trees, drink laudanum, or do drugs in general. However, {agent_name} is a strong environmentalist, and cares about the surroundings, asking others to carpool if possible. Therefore, {agent_name} always cleans and takes care of equipment, so they always want to maintain the appliance after they use it. Finally, {agent_name} loves books and always buys any books they can find.
    """

def build_agent(
    config: formative_memories.AgentConfig,
    model: language_model.LanguageModel,
    memory: associative_memory.AssociativeMemory,
    clock: game_clock.MultiIntervalClock,
    update_time_interval: datetime.timedelta,
) -> basic_agent.BasicAgent:
  """Build an agent.

  Args:
    config: The agent config to use.
    model: The language model to use.
    memory: The agent's memory object.
    clock: The clock to use.
    update_time_interval: Agent calls update every time this interval passes.

  Returns:
    An agent.
  """
  if not config.extras.get('main_character', False):
    raise ValueError('This function is meant for a main character '
                     'but it was called on a supporting character.')

  agent_name = config.name

  if len(config.goal) == '':
      full_prompt = get_prompt_forbidden(agent_name)
  elif 'money' in config.goal:
      full_prompt = get_prompt_game(agent_name)
  elif 'books' in config.goal:
      full_prompt = get_prompt_london(agent_name)
  else:
      full_prompt = get_prompt(agent_name)

  instructions = basic_agent__main_role.get_instructions(agent_name)

  time = generic_components.report_function.ReportFunction(
      name='Current time',
      function=clock.current_time_interval_str,
  )

  overarching_goal = generic_components.constant.ConstantComponent(
      state=config.goal, name='overarching goal')

  prompt = generic_components.constant.ConstantComponent(
      state=full_prompt,#get_prompt(agent_name), 
      name='behaviour constraints'
    )

  current_obs = agent_components.observation.Observation(
      agent_name=agent_name,
      clock_now=clock.now,
      memory=memory,
      timeframe=clock.get_step_size(),
      component_name='current observations',
  )
  summary_obs = agent_components.observation.ObservationSummary(
      agent_name=agent_name,
      model=model,
      clock_now=clock.now,
      memory=memory,
      components=[current_obs],
      timeframe_delta_from=datetime.timedelta(hours=4),
      timeframe_delta_until=datetime.timedelta(hours=1),
      component_name='summary of observations',
  )

  relevant_memories = agent_components.all_similar_memories.AllSimilarMemories(
      name='relevant memories',
      model=model,
      memory=memory,
      agent_name=agent_name,
      components=[summary_obs],
      clock_now=clock.now,
      num_memories_to_retrieve=10,
  )

  options_perception = (
      agent_components.options_perception.AvailableOptionsPerception(
          name=(f'\nQuestion: Which options are available to {agent_name} '
                'right now?\nAnswer'),
          model=model,
          memory=memory,
          agent_name=agent_name,
          components=[overarching_goal,
                      prompt,
                      current_obs,
                      summary_obs,
                      relevant_memories],
          clock_now=clock.now,
      )
  )
  best_option_perception = (
      agent_components.options_perception.BestOptionPerception(
          name=(f'\nQuestion: Of the options available to {agent_name}, and '
                'given their goal, which choice of action or strategy is '
                f'best for {agent_name} to take right now?\nAnswer'),
          model=model,
          memory=memory,
          agent_name=agent_name,
          components=[overarching_goal,
                      prompt,
                      current_obs,
                      summary_obs,
                      relevant_memories,
                      options_perception],
          clock_now=clock.now,
      )
  )
  information = generic_components.sequential.Sequential(
      name='information',
      components=[
          time,
          current_obs,
          summary_obs,
          relevant_memories,
          options_perception,
          best_option_perception,
      ]
  )

  agent = basic_agent.BasicAgent(
      model=model,
      agent_name=agent_name,
      clock=clock,
      verbose=False,
      components=[instructions,
                  overarching_goal,
                  prompt,
                  information],
      update_interval=update_time_interval
  )

  return agent