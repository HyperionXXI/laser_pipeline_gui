# core/ilda_profiles.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class IldaProfile:
    """
    Profil ILDA : regroupe les paramètres de base pour un mode de rendu.

    Pour l'instant, on expose surtout des paramètres géométriques et une
    couleur de base (index de palette ILDA). Le cœur du pipeline utilise
    encore directement les paramètres passés à export_project_to_ilda pour
    la géométrie : le profil sert surtout de structure pour la suite.
    """
    name: str
    fit_axis: str = "max"
    fill_ratio: float = 0.95
    min_rel_size: float = 0.01
    remove_outer_frame: bool = True
    frame_margin_rel: float = 0.02
#   base_color_index: int = 0  # index de couleur ILDA par défaut
    base_color_index: int = 7  # blanc (palette ILDA standard – dans LaserShowGen, 0 apparaît rouge)

ILDA_PROFILES: Dict[str, IldaProfile] = {
    # Mode actuel, comportement identique à ce que tu as aujourd'hui.
    "classic": IldaProfile(
        name="classic",
        fit_axis="max",
        fill_ratio=0.95,
        min_rel_size=0.01,
        remove_outer_frame=True,
        frame_margin_rel=0.02,
#       base_color_index=0,  # on reste sur l'index 0 (rouge dans LaserShowGen)
        base_color_index=7,  # blanc
    ),

    # Mode "arcade" – pour l'instant identique côté paramètres. On
    # l'utilisera ensuite pour des choix différents (couleurs, filtrage,
    # etc.).
    "arcade": IldaProfile(
        name="arcade",
        fit_axis="max",
        fill_ratio=0.95,
        min_rel_size=0.01,
        remove_outer_frame=True,
        frame_margin_rel=0.02,
#       base_color_index=0,
        base_color_index=7,
    ),

    "la_linea": IldaProfile(
        name="la_linea",
        fit_axis="max",
        fill_ratio=0.95,
        min_rel_size=0.01,
        remove_outer_frame=True,
        frame_margin_rel=0.02,
        base_color_index=1,  # blanc par défaut si pas de PNG
    ),

}


def get_ilda_profile(name: str | None) -> IldaProfile:
    """
    Retourne le profil ILDA pour `name`.

    - None ou nom inconnu → profil "classic".
    - Les noms sont traités en lower-case.
    """
    if not name:
        return ILDA_PROFILES["classic"]

    profile = ILDA_PROFILES.get(name.lower())
    if profile is None:
        return ILDA_PROFILES["classic"]

    return profile
