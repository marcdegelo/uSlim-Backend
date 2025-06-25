from flask import Blueprint

from paRoutes.iSlim.auth_routes import uSlimAuthRoutes
from paRoutes.iSlim.fitness_routes import uSlimFitnessRoutes
from paRoutes.iSlim.meal_routes import uSlimMealRoutes
from paRoutes.iSlim.util_routes import uSlimUtilsRoutes
from paRoutes.iSlim.steps_routes import uSlimStepsRoutes
from paRoutes.iSlim.map_routes import uSlimMapRoutes
from paRoutes.iSlim.profile_routes import uSlimProfileRoutes
from paRoutes.iSlim.survey_routes import uSlimSurveyRoutes
from paRoutes.iSlim.yoga_routes import uSlimYogaRoutes
from paRoutes.iSlim.workout_routes import uSlimWorkoutRoutes

uSlimRoutes = Blueprint("uSlimRoutes", __name__, url_prefix="/uSlim")

uSlimRoutes.register_blueprint(uSlimAuthRoutes)
uSlimRoutes.register_blueprint(uSlimFitnessRoutes)
uSlimRoutes.register_blueprint(uSlimMealRoutes)
uSlimRoutes.register_blueprint(uSlimUtilsRoutes)
uSlimRoutes.register_blueprint(uSlimStepsRoutes)
uSlimRoutes.register_blueprint(uSlimMapRoutes)
uSlimRoutes.register_blueprint(uSlimProfileRoutes)
uSlimRoutes.register_blueprint(uSlimSurveyRoutes)
uSlimRoutes.register_blueprint(uSlimYogaRoutes)
uSlimRoutes.register_blueprint(uSlimWorkoutRoutes)