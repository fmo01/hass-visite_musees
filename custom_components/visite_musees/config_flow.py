"""Visite Musées configuration and department options."""
from homeassistant import config_entries
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectSelectorMode
import voluptuous as vol

from .const import DOMAIN
from .museum_registry import DEFAULT_DEPARTMENTS
from .geo_departments import async_get_departments


def department_selector(departments, selected=()):
    choices = [{"value": item["code"], "label": f'{item["code"]} — {item["nom"]}'} for item in departments]
    # On an outage, preserve existing choices for editing without inventing names.
    present = {item["value"] for item in choices}
    choices.extend({"value": code, "label": code} for code in selected if code not in present)
    return SelectSelector(SelectSelectorConfig(
        options=choices,
        multiple=True,
        mode=SelectSelectorMode.DROPDOWN,
    ))


async def available_departments(hass):
    try:
        return await async_get_departments(hass)
    except Exception:
        return []


class VisiteMuseesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(
                title="Visite Musées", data={"departments": user_input["departments"]}
            )
        departments = await available_departments(self.hass)
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({
                vol.Required("departments", default=DEFAULT_DEPARTMENTS): vol.All(department_selector(departments, DEFAULT_DEPARTMENTS), vol.Length(min=1))
            })
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return VisiteMuseesOptionsFlow()


class VisiteMuseesOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data={"departments": user_input["departments"]})
        departments = self.config_entry.options.get(
            "departments", self.config_entry.data.get("departments", DEFAULT_DEPARTMENTS)
        )
        choices = await available_departments(self.hass)
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema({
                vol.Required("departments", default=departments): vol.All(department_selector(choices, departments), vol.Length(min=1))
            })
        )
