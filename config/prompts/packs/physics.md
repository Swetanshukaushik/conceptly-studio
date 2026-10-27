Fill `physics_plan` first. Use the motion simulator for ANY motion topic:
For every topic about motion, forces, energy, collisions, rotation, oscillations, gravitation or charged particles in fields, put a `sim` block in the scene instead of faking the motion with expressions: the simulator obeys Newton's laws, so the numbers in the picture are correct by construction (periods, accelerations, speeds, momentum). Rules:
- Choose realistic SI values from the narration (masses in kg, lengths in m). The scene's camera must show the whole motion: the visible width at distance d is given in the layout list.
- Put the quantity the narration talks about on screen: velocity arrows (`vectors:["v"]`), acceleration arrows, a trail, a force arrow, and a `graph` prefab plotting the matching quantity with `sim(k,i,X)`.
- Use `derivation` overlays for formulas and derivations (at most 4 lines per card, each line short).
- Make the motion fit the beat: distance = 1/2 a t^2 and flight time = 2 vy / g. Slow it with `timeScale` (for example 0.5) when the real motion is too fast to follow, and stop bodies with floors and walls so nothing leaves the picture.
- The camera frames the whole simulated motion automatically, so keep the motion compact: stop bodies with walls or floors (and friction) so they do not travel far after the event you are showing, and use `timeScale` so the event happens inside the beat. A body that rolls away for many metres makes everything tiny.
- A sim may run only part of the beat: `start` delays it, `timeScale` slows it down.
- Floors, walls and ramps MUST be sim `surfaces`: scene objects such as boxes do not stop bodies, so a ball would fall forever and the picture would go empty. Surfaces are drawn automatically; add other set pieces (a wall, labels, a hand) as normal objects. Bind a body to a prefab with `bind` when a plain ball or block is not enough.
Recipes (adapt them, do not copy numbers blindly):
{{SIM_RECIPES}}
