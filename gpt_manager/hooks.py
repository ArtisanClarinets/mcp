"""Frappe Hooks - Configuration for the GPT Manager app."""

app_name = 'gpt_manager'
app_title = 'GPT Manager'
app_publisher = 'Your Organization'
app_description = 'MCP Hub for integrating local and remote MCP servers'
app_email = 'developers@example.com'
app_license = 'MIT'

# Required apps
required_apps = ['frappe']

# Includes in <head>
# ------------------
# include js, css files in header of desk.html
# app_include_css = "/assets/gpt_manager/css/gpt_manager.css"
# app_include_js = "/assets/gpt_manager/js/gpt_manager.js"

# include js, css files in header of web template
# web_include_css = "/assets/gpt_manager/css/gpt_manager.css"
# web_include_js = "/assets/gpt_manager/js/gpt_manager.js"

# Include Frappe MCP as a dependency
# Note: frappe-mcp should be listed in pyproject.toml dependencies

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
#     "*": {
#         "on_update": "method",
#         "on_cancel": "method",
#         "on_trash": "method"
#     }
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
#     "all": [
#         "gpt_manager.tasks.all"
#     ],
#     "daily": [
#         "gpt_manager.tasks.daily"
#     ],
#     "hourly": [
#         "gpt_manager.tasks.hourly"
#     ],
#     "weekly": [
#         "gpt_manager.tasks.weekly"
#     ],
#     "monthly": [
#         "gpt_manager.tasks.monthly"
#     ],
# }

# Testing
# -------

# before_tests = "gpt_manager.install.before_tests"

# Overriding Methods
# ------------------
#
# override_whitelisted_methods = {
#     "frappe.desk.doctype.event.event.get_events": "gpt_manager.event.get_events"
# }

# Jinja Environment
# ------------------

# jinja = {
#     "methods": ["gpt_manager.utils.method"],
#     "filters": ["gpt_manager.utils.filter"]
# }

# Installation
# ------------

# before_install = "gpt_manager.install.before_install"
# after_install = "gpt_manager.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "gpt_manager.uninstall.before_uninstall"
# after_uninstall = "gpt_manager.uninstall.after_uninstall"

# User Data Protection
# --------------------

# user_data_fields = [
#     {
#         "doctype": "{doctype_1}",
#         "filter_by": "{filter_by}",
#         "redact_fields": ["{field_1}", "{field_2}"],
#         "partial": 1,
#     },
# ]
