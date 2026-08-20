
import os
import streamlit as st
import pandas as pd

from datetime import date, datetime, timezone
from supabase import create_client

from options import (
    DEFAULT_SPORT,
    SPORTS,
    BOOKMAKERS,
    get_leagues,
    get_scope_options,
    get_default_markets,
    get_periods,
    get_reasons,
    get_market_style,
    get_winner_side_options
)

from analytics import analysis_page
from suggestions import suggestions_page


# ==========================================
# PAGE CONFIG
# ==========================================

st.set_page_config(
    page_title="Bet Tracker",
    page_icon="🎯",
    layout="centered"
)


# ==========================================
# SUPABASE CONNECTION
# ==========================================

def get_secret(name):

    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass

    return os.getenv(name)


SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_PUBLISHABLE_KEY")


if not SUPABASE_URL or not SUPABASE_KEY:

    st.error(
        "Supabase credentials are missing."
    )

    st.stop()


supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# ==========================================
# SESSION STATE
# ==========================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "access_token" not in st.session_state:
    st.session_state.access_token = None

if "refresh_token" not in st.session_state:
    st.session_state.refresh_token = None

if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "user_email" not in st.session_state:
    st.session_state.user_email = None

if "delete_confirm_id" not in st.session_state:
    st.session_state.delete_confirm_id = None


# Restore auth after Streamlit rerun
if (
    st.session_state.logged_in
    and st.session_state.access_token
    and st.session_state.refresh_token
):

    try:

        session_response = (
            supabase.auth.set_session(
                st.session_state.access_token,
                st.session_state.refresh_token
            )
        )

        if session_response.session:

            st.session_state.access_token = (
                session_response
                .session
                .access_token
            )

            st.session_state.refresh_token = (
                session_response
                .session
                .refresh_token
            )

    except Exception:

        st.session_state.logged_in = False


# ==========================================
# HELPERS
# ==========================================

def now_utc():

    return (
        datetime
        .now(timezone.utc)
        .isoformat()
    )


def safe_index(
    options,
    value,
    default=0
):

    try:
        return options.index(value)

    except Exception:
        return default


def get_market_options(
    scope,
    sport=DEFAULT_SPORT
):
    return get_default_markets(
        sport,
        scope
    )



def outright_needs_second_selection(
    market,
    sport=DEFAULT_SPORT
):
    if market in [
        "Final Matchup",
        "Straight Forecast"
    ]:
        return True

    if (
        sport == "Basketball"
        and market.startswith("Top ")
        and market.endswith(" - Team")
    ):
        return True

    return False



def outright_selection_labels(
    market,
    sport=DEFAULT_SPORT
):
    if sport == "Tennis":
        if market == "Final Matchup":
            return ("Player 1", "Player 2")
        if market == "Straight Forecast":
            return ("Winner", "Runner-up")
        return ("Player", None)

    if sport == "Football":
        if market == "Final Matchup":
            return ("Team 1", "Team 2")
        if market == "Straight Forecast":
            return ("Winner", "Runner-up")
        if market in ["Top Goalscorer", "Top Assists"]:
            return ("Player", None)
        return ("Team", None)

    if market == "Final Matchup":
        return ("Team 1", "Team 2")

    if market == "Straight Forecast":
        return ("1st Place", "2nd Place")

    if (
        market.startswith("Top ")
        and market.endswith(" - Team")
    ):
        return ("Player", "Team")

    if market.startswith("Top "):
        return ("Player", None)

    return ("Team", None)



def format_bet_selection(
    bet
):

    scope = bet.get("scope")

    market = (
        bet.get("market")
        or ""
    )

    subject = (
        bet.get("subject")
        or ""
    )

    selection_2 = (
        bet.get("selection_2")
        or ""
    )

    side = bet.get("side")
    line = bet.get("line")


    if scope == "OUTRIGHT":

        if market == "Final Matchup":

            if selection_2:

                return (
                    f"{subject} vs "
                    f"{selection_2}"
                )

            return subject


        if market == "Straight Forecast":

            if selection_2:

                return (
                    f"1st: {subject} | "
                    f"2nd: {selection_2}"
                )

            return (
                f"1st: {subject}"
            )


        if (
            market.startswith("Top ")
            and market.endswith(
                " - Team"
            )
        ):

            if selection_2:

                return (
                    f"{subject} "
                    f"({selection_2})"
                )

            return subject


        return subject


    text_value = side or ""


    if line is not None:

        text_value = (
            f"{text_value} "
            f"{float(line):g}"
        ).strip()


    return text_value


def calculate_metrics(
    market_odds,
    my_odds=None,
    tipster_posted_odds=None
):

    p_market = (
        1 / float(market_odds)
    )

    p_you = None
    edge_pp = None
    ev_pct = None

    if my_odds:

        p_you = (
            1 / float(my_odds)
        )

        edge_pp = (
            p_you - p_market
        ) * 100

        ev_pct = (
            p_you
            * float(market_odds)
            - 1
        ) * 100


    price_deterioration_pp = None

    if tipster_posted_odds:

        posted_probability = (
            1
            / float(
                tipster_posted_odds
            )
        )

        price_deterioration_pp = (
            p_market
            - posted_probability
        ) * 100


    return {

        "p_market":
            p_market,

        "p_you":
            p_you,

        "edge_pp":
            edge_pp,

        "ev_pct":
            ev_pct,

        "price_deterioration_pp":
            price_deterioration_pp
    }


def calculate_profit(
    result,
    stake,
    market_odds
):

    stake = float(stake)
    odds = float(market_odds)

    if result == "Win":

        return round(
            stake * (odds - 1),
            2
        )

    if result == "Loss":

        return round(
            -stake,
            2
        )

    return 0.0


# ==========================================
# LOGIN
# ==========================================

def login_page():

    st.title(
        "🎯 Bet Tracker"
    )

    st.caption(
        "Sign in to your personal tracker"
    )


    with st.form(
        "login_form"
    ):

        email = st.text_input(
            "Email",
            autocomplete="username"
        )

        password = st.text_input(
            "Password",
            type="password",
            autocomplete="current-password"
        )

        submitted = (
            st.form_submit_button(
                "Login",
                use_container_width=True
            )
        )


    st.caption(
        "💾 Your browser can offer to save the login "
        "for this device."
    )


    if submitted:

        if not email or not password:

            st.warning(
                "Enter email and password."
            )

            return


        try:

            response = (
                supabase
                .auth
                .sign_in_with_password({
                    "email":
                        email,

                    "password":
                        password
                })
            )


            if (
                response.session
                and response.user
            ):

                st.session_state.logged_in = (
                    True
                )

                st.session_state.access_token = (
                    response
                    .session
                    .access_token
                )

                st.session_state.refresh_token = (
                    response
                    .session
                    .refresh_token
                )

                st.session_state.user_id = (
                    response.user.id
                )

                st.session_state.user_email = (
                    response.user.email
                )

                st.rerun()


        except Exception as e:

            st.error(
                f"Login failed: {e}"
            )


def logout():

    try:

        supabase.auth.sign_out()

    except Exception:
        pass

    st.session_state.clear()

    st.rerun()


# ==========================================
# TIPSTERS
# ==========================================

def load_tipsters():

    try:

        response = (
            supabase
            .table("tipsters")
            .select("id,name")
            .order("name")
            .execute()
        )

        return response.data or []

    except Exception:

        return []


def create_tipster(name):

    name = name.strip()

    if not name:
        return None


    response = (
        supabase
        .table("tipsters")
        .insert({

            "user_id":
                st.session_state.user_id,

            "name":
                name
        })
        .execute()
    )


    if response.data:

        return response.data[0]

    return None


# ==========================================
# COUNTERS
# ==========================================

def get_total_bets_count():

    response = (
        supabase
        .table("bets")
        .select(
            "id",
            count="exact"
        )
        .eq(
            "is_deleted",
            False
        )
        .execute()
    )

    return response.count or 0


def get_pending_bets_count():

    response = (
        supabase
        .table("bets")
        .select(
            "id",
            count="exact"
        )
        .eq(
            "is_deleted",
            False
        )
        .eq(
            "result",
            "Pending"
        )
        .execute()
    )

    return response.count or 0


def get_settled_bets_count():

    response = (
        supabase
        .table("bets")
        .select(
            "id",
            count="exact"
        )
        .eq(
            "is_deleted",
            False
        )
        .neq(
            "result",
            "Pending"
        )
        .execute()
    )

    return response.count or 0


# ==========================================
# LOAD BETS
# ==========================================

def load_pending_bets():

    try:

        response = (
            supabase
            .table("bets")
            .select("*")
            .eq(
                "is_deleted",
                False
            )
            .eq(
                "result",
                "Pending"
            )
            .order(
                "bet_date",
                desc=False
            )
            .order(
                "bet_number",
                desc=True
            )
            .execute()
        )

        return response.data or []


    except Exception as e:

        st.error(
            f"Could not load pending bets: {e}"
        )

        return []


def load_history_bets():

    try:

        response = (
            supabase
            .table("bets")
            .select("*")
            .eq(
                "is_deleted",
                False
            )
            .neq(
                "result",
                "Pending"
            )
            .order(
                "bet_date",
                desc=True
            )
            .order(
                "bet_number",
                desc=True
            )
            .execute()
        )

        return response.data or []


    except Exception as e:

        st.error(
            f"Could not load history: {e}"
        )

        return []


def load_active_bets():

    try:

        response = (
            supabase
            .table("bets")
            .select("*")
            .eq(
                "is_deleted",
                False
            )
            .order(
                "bet_date",
                desc=True
            )
            .order(
                "bet_number",
                desc=True
            )
            .execute()
        )

        return response.data or []


    except Exception as e:

        st.error(
            f"Could not load bets: {e}"
        )

        return []


def load_deleted_bets():

    try:

        response = (
            supabase
            .table("bets")
            .select("*")
            .eq(
                "is_deleted",
                True
            )
            .order(
                "deleted_at",
                desc=True
            )
            .execute()
        )

        return response.data or []


    except Exception as e:

        st.error(
            f"Could not load Trash: {e}"
        )

        return []


# ==========================================
# SETTLE
# ==========================================

def settle_bet(
    bet_id,
    result,
    stake,
    market_odds
):

    profit = calculate_profit(
        result,
        stake,
        market_odds
    )


    response = (
        supabase
        .table("bets")
        .update({

            "result":
                result,

            "profit":
                profit,

            "settled_at":
                now_utc(),

            "updated_at":
                now_utc()
        })
        .eq(
            "id",
            bet_id
        )
        .eq(
            "user_id",
            st.session_state.user_id
        )
        .execute()
    )

    return response.data



# ==========================================
# CASHOUT
# ==========================================

def settle_cashout(
    bet_id,
    stake,
    cashout_return
):

    stake = float(stake)
    cashout_return = float(
        cashout_return
    )

    profit = round(
        cashout_return - stake,
        2
    )

    timestamp = now_utc()

    response = (
        supabase
        .table("bets")
        .update({

            "result":
                "Cashout",

            "cashout_return":
                cashout_return,

            "profit":
                profit,

            "cashout_at":
                timestamp,

            "settled_at":
                timestamp,

            "updated_at":
                timestamp
        })
        .eq(
            "id",
            bet_id
        )
        .eq(
            "user_id",
            st.session_state.user_id
        )
        .execute()
    )

    return response.data


# ==========================================
# SOFT DELETE / RESTORE
# ==========================================

def soft_delete_bet(bet_id):

    response = (
        supabase
        .table("bets")
        .update({

            "is_deleted":
                True,

            "deleted_at":
                now_utc(),

            "updated_at":
                now_utc()
        })
        .eq(
            "id",
            bet_id
        )
        .eq(
            "user_id",
            st.session_state.user_id
        )
        .execute()
    )

    return response.data


def restore_bet(bet_id):

    response = (
        supabase
        .table("bets")
        .update({

            "is_deleted":
                False,

            "deleted_at":
                None,

            "updated_at":
                now_utc()
        })
        .eq(
            "id",
            bet_id
        )
        .eq(
            "user_id",
            st.session_state.user_id
        )
        .execute()
    )

    return response.data



# ==========================================
# ENTRY AUTOCOMPLETE
# ==========================================

def load_entry_suggestions(
    sport
):
    rows = []
    page_size = 1000
    start = 0

    try:
        while True:
            response = (
                supabase
                .table("bets")
                .select(
                    "event,scope,subject,"
                    "selection_2,market,sport"
                )
                .eq("is_deleted", False)
                .eq("sport", sport)
                .range(
                    start,
                    start + page_size - 1
                )
                .execute()
            )

            page = response.data or []
            rows.extend(page)

            if len(page) < page_size:
                break

            start += page_size

    except Exception:
        rows = []

    regular_events = []
    outright_events = []
    players = []
    teams = []

    for bet in rows:
        scope = bet.get("scope")
        event = (bet.get("event") or "").strip()
        subject = (bet.get("subject") or "").strip()
        selection_2 = (bet.get("selection_2") or "").strip()
        market = bet.get("market") or ""

        if event:
            if scope == "OUTRIGHT":
                outright_events.append(event)
            else:
                regular_events.append(event)

        if scope == "PLAYER":
            if subject:
                players.append(subject)

        elif scope == "TEAM":
            if subject:
                teams.append(subject)

        elif scope == "OUTRIGHT":
            if sport == "Tennis":
                if subject:
                    players.append(subject)
                if selection_2:
                    players.append(selection_2)

            elif (
                sport == "Football"
                and market in ["Top Goalscorer", "Top Assists"]
            ):
                if subject:
                    players.append(subject)

            elif (
                sport == "Basketball"
                and market.startswith("Top ")
            ):
                if subject:
                    players.append(subject)
                if market.endswith(" - Team") and selection_2:
                    teams.append(selection_2)

            elif market in ["Final Matchup", "Straight Forecast"]:
                if subject:
                    teams.append(subject)
                if selection_2:
                    teams.append(selection_2)

            else:
                if subject:
                    teams.append(subject)

    def clean(values):
        unique = {}
        for value in values:
            value = str(value).strip()
            if not value:
                continue
            key = value.casefold()
            if key not in unique:
                unique[key] = value
        return sorted(
            unique.values(),
            key=lambda x: x.casefold()
        )

    return {
        "regular_events": clean(regular_events),
        "outright_events": clean(outright_events),
        "players": clean(players),
        "teams": clean(teams)
    }



# ==========================================
# ADD BET
# ==========================================


# ==========================================
# STICKY ENTRY / CUSTOM OPTIONS
# ==========================================

def _remember_entry_value(
    bucket,
    value,
    sport=None,
    scope=None
):
    if value is None:
        return

    value = str(value).strip()

    if not value:
        return

    memory_key = "::".join([
        str(sport or "ALL"),
        str(scope or "ALL"),
        str(bucket)
    ])

    if "_recent_entry_suggestions" not in st.session_state:
        st.session_state["_recent_entry_suggestions"] = {}

    recent = st.session_state["_recent_entry_suggestions"]
    values = recent.get(memory_key, [])
    existing = {str(v).casefold() for v in values}

    if value.casefold() not in existing:
        values.append(value)

    recent[memory_key] = values



def _merge_recent_entry_options(
    bucket,
    values,
    sport=None,
    scope=None
):
    values = list(values or [])

    memory_key = "::".join([
        str(sport or "ALL"),
        str(scope or "ALL"),
        str(bucket)
    ])

    recent = (
        st.session_state
        .get("_recent_entry_suggestions", {})
        .get(memory_key, [])
    )

    combined = []
    seen = set()

    for value in values + recent:
        if value is None:
            continue

        value = str(value).strip()

        if not value:
            continue

        key = value.casefold()

        if key in seen:
            continue

        seen.add(key)
        combined.append(value)

    return combined



def load_user_league_options(
    sport
):
    saved_leagues = []
    page_size = 1000
    start = 0

    try:
        while True:
            response = (
                supabase
                .table("bets")
                .select("league")
                .eq("is_deleted", False)
                .eq("sport", sport)
                .range(
                    start,
                    start + page_size - 1
                )
                .execute()
            )

            page = response.data or []

            for row in page:
                league = (row.get("league") or "").strip()
                if league:
                    saved_leagues.append(league)

            if len(page) < page_size:
                break

            start += page_size

    except Exception:
        pass

    return _merge_recent_entry_options(
        "leagues",
        get_leagues(sport) + saved_leagues,
        sport=sport
    )


def load_user_market_options(
    sport,
    scope
):
    saved_markets = []
    page_size = 1000
    start = 0

    try:
        while True:
            response = (
                supabase
                .table("bets")
                .select("market")
                .eq("is_deleted", False)
                .eq("sport", sport)
                .eq("scope", scope)
                .range(
                    start,
                    start + page_size - 1
                )
                .execute()
            )

            page = response.data or []

            for row in page:
                market = (row.get("market") or "").strip()
                if market:
                    saved_markets.append(market)

            if len(page) < page_size:
                break

            start += page_size

    except Exception:
        pass

    return _merge_recent_entry_options(
        "markets",
        get_default_markets(
            sport,
            scope
        ) + saved_markets,
        sport=sport,
        scope=scope
    )


def _include_session_option(
    options,
    key
):
    options = list(options or [])
    current = st.session_state.get(key)

    if current is None:
        return options

    current = str(current).strip()

    if not current:
        return options

    existing = {
        str(value).casefold()
        for value in options
    }

    if current.casefold() not in existing:
        options.append(current)

    return options


def infer_saved_custom_market_format(
    sport,
    scope,
    market
):
    try:
        response = (
            supabase
            .table("bets")
            .select("side,line")
            .eq("is_deleted", False)
            .eq("sport", sport)
            .eq("scope", scope)
            .eq("market", market)
            .limit(1)
            .execute()
        )

        rows = response.data or []

        if not rows:
            return "Over / Under"

        row = rows[0]
        side = row.get("side") or ""
        line = row.get("line")

        if side in ["Yes", "No"]:
            return "Yes / No"

        winner_sides = get_winner_side_options(
            sport,
            market
        )

        if side in winner_sides:
            if line is None:
                return "Winner / Selection"
            return "Handicap / Spread"

    except Exception:
        pass

    return "Over / Under"




def add_bet_page():

    st.header("➕ Add Bet")

    def ensure_valid(
        key,
        options,
        default=None
    ):
        if key not in st.session_state:
            return

        current = st.session_state[key]

        if current in options:
            return

        if default is not None:
            st.session_state[key] = default
        else:
            st.session_state.pop(key, None)

    ensure_valid(
        "add_sport",
        SPORTS,
        DEFAULT_SPORT
    )

    sport = st.selectbox(
        "Sport",
        SPORTS,
        key="add_sport"
    )

    previous_sport = (
        st.session_state
        .get("_add_last_sport")
    )

    if previous_sport is None:
        st.session_state[
            "_add_last_sport"
        ] = sport

    elif previous_sport != sport:
        dependent_keys = [
            "add_scope",
            "add_regular_event",
            "add_outright_event",
            "add_player",
            "add_team",
            "add_outright_market",
            "add_outright_subject",
            "add_outright_selection_2",
            "add_market_player",
            "add_market_team",
            "add_market_match",
            "add_period",
            "add_side",
            "add_line",
            "add_self_primary_reason",
            "add_self_secondary_reason",
            "add_tipster_primary_reason",
            "add_tipster_secondary_reason"
        ]

        for key in dependent_keys:
            st.session_state.pop(
                key,
                None
            )

        st.session_state[
            "_add_last_sport"
        ] = sport

        st.rerun()

    col1, col2 = st.columns(2)

    with col1:
        bet_date = st.date_input(
            "Bet Date",
            value=date.today(),
            key="add_bet_date"
        )

    with col2:
        league_options = (
            load_user_league_options(
                sport
            )
        )

        league_key = (
            f"add_league_"
            f"{sport.lower()}"
        )

        league_options = (
            _include_session_option(
                league_options,
                league_key
            )
        )

        league = st.selectbox(
            "League / Tour",
            league_options,
            accept_new_options=True,
            key=league_key
        )

    is_live = st.checkbox(
        "🔴 Live Bet",
        value=False,
        key="add_is_live",
        help=(
            "Leave unchecked for a pre-live bet. "
            "Check it only if the bet was placed live."
        )
    )

    scope_options = (
        get_scope_options(
            sport
        )
    )

    ensure_valid(
        "add_scope",
        scope_options,
        scope_options[0]
    )

    scope = st.radio(
        "Bet Type",
        scope_options,
        horizontal=True,
        key="add_scope"
    )

    entry_suggestions = (
        load_entry_suggestions(
            sport
        )
    )

    for _bucket in [
        "regular_events",
        "outright_events",
        "players",
        "teams"
    ]:
        entry_suggestions[_bucket] = (
            _merge_recent_entry_options(
                _bucket,
                entry_suggestions.get(
                    _bucket,
                    []
                ),
                sport=sport
            )
        )

    event_options = (
        entry_suggestions["outright_events"]
        if scope == "OUTRIGHT"
        else entry_suggestions["regular_events"]
    )

    event_key = (
        "add_outright_event"
        if scope == "OUTRIGHT"
        else "add_regular_event"
    )

    event_options = (
        _include_session_option(
            event_options,
            event_key
        )
    )

    event = st.selectbox(
        (
            "Tournament / Event"
            if (
                sport == "Tennis"
                and scope == "OUTRIGHT"
            )
            else (
                "Competition / Event"
                if scope == "OUTRIGHT"
                else "Event"
            )
        ),
        event_options,
        index=None,
        placeholder=(
            "Search or enter tournament..."
            if (
                sport == "Tennis"
                and scope == "OUTRIGHT"
            )
            else (
                "Search or enter competition..."
                if scope == "OUTRIGHT"
                else "Search or enter matchup..."
            )
        ),
        accept_new_options=True,
        key=event_key
    )

    st.divider()

    subject = None
    selection_2 = None
    line = None
    side = None

    if scope == "OUTRIGHT":
        market_options = (
            load_user_market_options(
                sport,
                scope
            )
        )

        market_options = (
            _include_session_option(
                market_options,
                "add_outright_market"
            )
        )

        market = st.selectbox(
            "Outright Market",
            market_options,
            accept_new_options=True,
            key="add_outright_market"
        )

        label_1, label_2 = (
            outright_selection_labels(
                market,
                sport
            )
        )

        if (
            sport == "Tennis"
            or label_1 == "Player"
            or label_1.startswith("Player ")
        ):
            outright_options_1 = (
                entry_suggestions["players"]
            )
        else:
            outright_options_1 = (
                entry_suggestions["teams"]
            )

        outright_options_1 = (
            _include_session_option(
                outright_options_1,
                "add_outright_subject"
            )
        )

        subject = st.selectbox(
            label_1,
            outright_options_1,
            index=None,
            placeholder=(
                f"Search or enter "
                f"{label_1.lower()}..."
            ),
            accept_new_options=True,
            key="add_outright_subject"
        )

        if label_2:
            second_options = (
                entry_suggestions["players"]
                if sport == "Tennis"
                else entry_suggestions["teams"]
            )

            second_options = (
                _include_session_option(
                    second_options,
                    "add_outright_selection_2"
                )
            )

            selection_2 = st.selectbox(
                label_2,
                second_options,
                index=None,
                placeholder=(
                    f"Search or enter "
                    f"{label_2.lower()}..."
                ),
                accept_new_options=True,
                key="add_outright_selection_2"
            )

        period = "Full Competition"

        st.caption(
            "🏆 This bet will be stored "
            "separately from regular "
            "pending bets."
        )

    else:
        if scope == "PLAYER":
            player_options = (
                _include_session_option(
                    entry_suggestions["players"],
                    "add_player"
                )
            )

            subject = st.selectbox(
                "Player",
                player_options,
                index=None,
                placeholder=(
                    "Search or enter player..."
                ),
                accept_new_options=True,
                key="add_player"
            )

        elif scope == "TEAM":
            team_options = (
                _include_session_option(
                    entry_suggestions["teams"],
                    "add_team"
                )
            )

            subject = st.selectbox(
                "Team",
                team_options,
                index=None,
                placeholder=(
                    "Search or enter team..."
                ),
                accept_new_options=True,
                key="add_team"
            )

        market_key = (
            f"add_market_"
            f"{scope.lower()}"
        )

        market_options = (
            load_user_market_options(
                sport,
                scope
            )
        )

        market_options = (
            _include_session_option(
                market_options,
                market_key
            )
        )

        market = st.selectbox(
            "Market",
            market_options,
            accept_new_options=True,
            key=market_key
        )

        periods = get_periods(
            sport
        )

        ensure_valid(
            "add_period",
            periods,
            periods[0]
        )

        period = st.selectbox(
            "Period",
            periods,
            key="add_period"
        )

        default_markets = (
            get_default_markets(
                sport,
                scope
            )
        )

        is_custom_market = (
            market not in default_markets
        )

        if is_custom_market:
            format_options = [
                "Over / Under",
                "Winner / Selection",
                "Handicap / Spread",
                "Yes / No"
            ]

            format_key = (
                "add_custom_market_format_"
                + sport
                + "_"
                + scope
                + "_"
                + market
            )

            if format_key not in st.session_state:
                st.session_state[
                    format_key
                ] = (
                    infer_saved_custom_market_format(
                        sport,
                        scope,
                        market
                    )
                )

            custom_market_format = (
                st.selectbox(
                    "Market Format",
                    format_options,
                    key=format_key
                )
            )

            style_map = {
                "Over / Under": "total",
                "Winner / Selection": "winner",
                "Handicap / Spread": "handicap",
                "Yes / No": "yes_no"
            }

            market_style = (
                style_map[
                    custom_market_format
                ]
            )
        else:
            market_style = (
                get_market_style(
                    sport,
                    scope,
                    market
                )
            )

        if market_style == "winner":
            side_options = (
                get_winner_side_options(
                    sport,
                    market
                )
            )

            ensure_valid(
                "add_side",
                side_options,
                side_options[0]
            )

            side = st.radio(
                "Selection",
                side_options,
                horizontal=True,
                key="add_side"
            )

        elif market_style == "handicap":
            side_options = (
                get_winner_side_options(
                    sport,
                    market
                )
            )

            ensure_valid(
                "add_side",
                side_options,
                side_options[0]
            )

            side = st.radio(
                "Selection",
                side_options,
                horizontal=True,
                key="add_side"
            )

            line = st.number_input(
                "Line",
                step=0.5,
                format="%.1f",
                key="add_line"
            )

        elif market_style == "yes_no":
            side_options = [
                "Yes",
                "No"
            ]

            ensure_valid(
                "add_side",
                side_options,
                "Yes"
            )

            side = st.radio(
                "Selection",
                side_options,
                horizontal=True,
                key="add_side"
            )

        else:
            side_options = [
                "Over",
                "Under"
            ]

            ensure_valid(
                "add_side",
                side_options,
                "Over"
            )

            side = st.radio(
                "Side",
                side_options,
                horizontal=True,
                key="add_side"
            )

            line = st.number_input(
                "Line",
                step=0.5,
                format="%.1f",
                key="add_line"
            )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        ensure_valid(
            "add_bookmaker",
            BOOKMAKERS,
            BOOKMAKERS[0]
        )

        bookmaker = st.selectbox(
            "Bookmaker",
            BOOKMAKERS,
            key="add_bookmaker"
        )

    with col2:
        market_odds = st.number_input(
            "Odds Taken",
            min_value=1.01,
            value=1.90,
            step=0.01,
            format="%.2f",
            key="add_market_odds"
        )

    origin = st.radio(
        "Origin",
        ["SELF", "TIPSTER"],
        horizontal=True,
        key="add_origin"
    )

    my_odds = None
    tipster_id = None
    tipster_posted_odds = None
    has_own_reasoning = False
    primary_reason = None
    secondary_reason = None
    confidence = None

    reasons = get_reasons(
        sport
    )

    if origin == "SELF":
        my_odds = st.number_input(
            "My Fair Odds",
            min_value=1.01,
            value=1.80,
            step=0.01,
            format="%.2f",
            key="add_self_fair_odds"
        )

        confidence_options = [
            "Low",
            "Medium",
            "High"
        ]

        ensure_valid(
            "add_self_confidence",
            confidence_options,
            "Medium"
        )

        confidence = st.radio(
            "Confidence",
            confidence_options,
            horizontal=True,
            key="add_self_confidence"
        )

        reason_options = (
            ["Select reason..."]
            + reasons
        )

        ensure_valid(
            "add_self_primary_reason",
            reason_options,
            "Projection Edge"
        )

        primary_reason = st.selectbox(
            "Primary Reason",
            reason_options,
            key="add_self_primary_reason"
        )

        secondary_options = (
            ["None"]
            + [
                reason
                for reason in reasons
                if reason != primary_reason
            ]
        )

        ensure_valid(
            "add_self_secondary_reason",
            secondary_options,
            "None"
        )

        secondary_reason = st.selectbox(
            "Secondary Reason",
            secondary_options,
            key="add_self_secondary_reason"
        )

        has_own_reasoning = True

    else:
        tipsters = load_tipsters()

        tipster_map = {
            t["name"]: t["id"]
            for t in tipsters
        }

        existing_names = list(
            tipster_map.keys()
        )

        tipster_options = (
            ["+ Add new tipster"]
            + existing_names
        )

        ensure_valid(
            "add_tipster_choice",
            tipster_options,
            tipster_options[0]
        )

        tipster_choice = st.selectbox(
            "Tipster",
            tipster_options,
            key="add_tipster_choice"
        )

        if tipster_choice == "+ Add new tipster":
            new_tipster = st.text_input(
                "New Tipster Name",
                key="add_new_tipster"
            )

            if st.button(
                "Save Tipster",
                key="save_tipster_button"
            ):
                try:
                    record = create_tipster(
                        new_tipster
                    )

                    if record:
                        st.success(
                            "Tipster saved."
                        )
                        st.rerun()

                except Exception as e:
                    st.error(str(e))

        else:
            tipster_id = (
                tipster_map[
                    tipster_choice
                ]
            )

        add_posted_odds = st.checkbox(
            "I know the tipster's "
            "posted odds",
            key="add_tipster_has_posted_odds"
        )

        if add_posted_odds:
            tipster_posted_odds = (
                st.number_input(
                    "Tipster Posted Odds",
                    min_value=1.01,
                    value=1.90,
                    step=0.01,
                    format="%.2f",
                    key="add_tipster_posted_odds"
                )
            )

        tipster_confidence_options = [
            "N/A",
            "Low",
            "Medium",
            "High"
        ]

        ensure_valid(
            "add_tipster_confidence",
            tipster_confidence_options,
            "N/A"
        )

        confidence = st.radio(
            "Your Confidence",
            tipster_confidence_options,
            horizontal=True,
            key="add_tipster_confidence"
        )

        has_own_reasoning = st.checkbox(
            "I also have my own "
            "reasoning for this bet",
            key="add_tipster_own_reasoning"
        )

        if has_own_reasoning:
            reason_options = (
                ["Select reason..."]
                + reasons
            )

            ensure_valid(
                "add_tipster_primary_reason",
                reason_options,
                "Projection Edge"
            )

            primary_reason = st.selectbox(
                "Primary Reason",
                reason_options,
                key="add_tipster_primary_reason"
            )

            secondary_options = (
                ["None"]
                + [
                    reason
                    for reason in reasons
                    if reason != primary_reason
                ]
            )

            ensure_valid(
                "add_tipster_secondary_reason",
                secondary_options,
                "None"
            )

            secondary_reason = st.selectbox(
                "Secondary Reason",
                secondary_options,
                key="add_tipster_secondary_reason"
            )

    st.divider()

    stake = st.number_input(
        "Stake",
        min_value=0.01,
        value=10.00,
        step=1.00,
        key="add_stake"
    )

    notes = st.text_area(
        "Notes",
        placeholder="Optional",
        key="add_notes"
    )

    if origin == "SELF":
        preview = calculate_metrics(
            market_odds,
            my_odds
        )

        st.info(
            f"Market probability: "
            f"{preview['p_market']*100:.2f}% | "
            f"My probability: "
            f"{preview['p_you']*100:.2f}% | "
            f"Probability Edge: "
            f"{preview['edge_pp']:.2f} pp | "
            f"EV: "
            f"{preview['ev_pct']:.2f}%"
        )

    if st.button(
        "💾 SAVE BET",
        type="primary",
        use_container_width=True,
        key="save_bet_button"
    ):
        if not (
            event
            and str(event).strip()
        ):
            st.error(
                "Event / Competition "
                "is required."
            )
            return

        if (
            scope in ["PLAYER", "TEAM"]
            and not (
                subject
                and str(subject).strip()
            )
        ):
            st.error(
                "Player / Team is required."
            )
            return

        if scope == "OUTRIGHT":
            if not (
                subject
                and str(subject).strip()
            ):
                st.error(
                    "Outright selection "
                    "is required."
                )
                return

            if (
                outright_needs_second_selection(
                    market,
                    sport
                )
                and not (
                    selection_2
                    and str(selection_2).strip()
                )
            ):
                st.error(
                    "The second selection "
                    "is required."
                )
                return

        if (
            origin == "TIPSTER"
            and tipster_id is None
        ):
            st.error(
                "Select or create a tipster."
            )
            return

        if (
            primary_reason == "Select reason..."
            and (
                origin == "SELF"
                or (
                    origin == "TIPSTER"
                    and has_own_reasoning
                )
            )
        ):
            st.error(
                "Select a Primary Reason."
            )
            return

        metrics = calculate_metrics(
            market_odds,
            my_odds,
            tipster_posted_odds
        )

        record = {
            "user_id": st.session_state.user_id,
            "bet_date": bet_date.isoformat(),
            "is_live": bool(is_live),
            "sport": sport,
            "league": league,
            "event": str(event).strip(),
            "scope": scope,
            "subject": (
                str(subject).strip()
                if subject
                else None
            ),
            "selection_2": (
                str(selection_2).strip()
                if selection_2
                else None
            ),
            "market": market,
            "period": period,
            "side": side,
            "line": line,
            "bookmaker": bookmaker,
            "market_odds": market_odds,
            "my_odds": my_odds,
            "origin": origin,
            "tipster_id": tipster_id,
            "tipster_posted_odds": tipster_posted_odds,
            "confidence": confidence,
            "has_own_reasoning": has_own_reasoning,
            "primary_reason": (
                None
                if primary_reason == "Select reason..."
                else primary_reason
            ),
            "secondary_reason": (
                None
                if secondary_reason in [None, "None"]
                else secondary_reason
            ),
            "stake": stake,
            "result": "Pending",
            "p_market": metrics["p_market"],
            "p_you": metrics["p_you"],
            "edge_pp": metrics["edge_pp"],
            "ev_pct": metrics["ev_pct"],
            "price_deterioration_pp": (
                metrics[
                    "price_deterioration_pp"
                ]
            ),
            "profit": 0,
            "notes": (
                notes.strip()
                if notes.strip()
                else None
            )
        }

        try:
            response = (
                supabase
                .table("bets")
                .insert(record)
                .execute()
            )

            if response.data:
                _remember_entry_value(
                    "leagues",
                    league,
                    sport=sport
                )

                _remember_entry_value(
                    "markets",
                    market,
                    sport=sport,
                    scope=scope
                )

                if scope == "OUTRIGHT":
                    _remember_entry_value(
                        "outright_events",
                        event,
                        sport=sport
                    )

                    if sport == "Tennis":
                        _remember_entry_value(
                            "players",
                            subject,
                            sport=sport
                        )
                        _remember_entry_value(
                            "players",
                            selection_2,
                            sport=sport
                        )

                    elif (
                        sport == "Football"
                        and market in [
                            "Top Goalscorer",
                            "Top Assists"
                        ]
                    ):
                        _remember_entry_value(
                            "players",
                            subject,
                            sport=sport
                        )

                    elif (
                        sport == "Basketball"
                        and market.startswith("Top ")
                    ):
                        _remember_entry_value(
                            "players",
                            subject,
                            sport=sport
                        )

                        if market.endswith(" - Team"):
                            _remember_entry_value(
                                "teams",
                                selection_2,
                                sport=sport
                            )

                    else:
                        _remember_entry_value(
                            "teams",
                            subject,
                            sport=sport
                        )
                        _remember_entry_value(
                            "teams",
                            selection_2,
                            sport=sport
                        )

                else:
                    _remember_entry_value(
                        "regular_events",
                        event,
                        sport=sport
                    )

                    if scope == "PLAYER":
                        _remember_entry_value(
                            "players",
                            subject,
                            sport=sport
                        )

                    elif scope == "TEAM":
                        _remember_entry_value(
                            "teams",
                            subject,
                            sport=sport
                        )

                st.success(
                    "✅ Bet saved successfully!"
                )

                st.write(
                    f"Total Bets: "
                    f"{get_total_bets_count()}"
                )

        except Exception as e:
            st.error(
                f"Could not save bet: {e}"
            )





# ==========================================
# PENDING
# ==========================================

def render_pending_group(
    bets,
    tipster_map
):

    if not bets:

        st.info(
            "No pending bets "
            "in this category."
        )

        return


    for bet in bets:

        st.divider()


        if bet["scope"] == "OUTRIGHT":

            title = (
                bet["event"]
                or "Outright"
            )

        elif bet["scope"] == "MATCH":

            title = bet["event"]

        else:

            title = bet["subject"]


        st.subheader(
            title
        )


        selection_text = (
            format_bet_selection(
                bet
            )
        )


        if selection_text:

            st.write(
                f"**{bet['market']}** | "
                f"{selection_text}"
            )

        else:

            st.write(
                f"**{bet['market']}**"
            )


        if bet["scope"] == "OUTRIGHT":

            st.caption(
                f"{bet.get('sport') or DEFAULT_SPORT} | "
                f"🏆 {bet['league']} | "
                f"{bet['bookmaker']}"
            )

        else:

            st.caption(
                f"{bet.get('sport') or DEFAULT_SPORT} | "
                f"{bet['league']} | "
                f"{bet['period']} | "
                f"{bet['bookmaker']}"
            )


        c1, c2, c3 = st.columns(3)


        with c1:

            st.metric(
                "Odds",
                f"{float(bet['market_odds']):.2f}"
            )


        with c2:

            st.metric(
                "Stake",
                f"{float(bet['stake']):.2f}"
            )


        with c3:

            st.metric(
                "Date",
                bet["bet_date"]
            )


        if bet["origin"] == "SELF":

            if bet["my_odds"] is not None:

                st.caption(
                    f"My Fair Odds: "
                    f"{float(bet['my_odds']):.2f} | "
                    f"EV: "
                    f"{float(bet['ev_pct']):.2f}%"
                )


        else:

            tipster_name = (
                tipster_map.get(
                    bet["tipster_id"],
                    "Unknown Tipster"
                )
            )

            st.caption(
                f"Tipster: "
                f"{tipster_name}"
            )


        # ==================================
        # RESULT BUTTONS
        # ==================================

        win_col, loss_col, void_col = (
            st.columns(3)
        )


        with win_col:

            if st.button(
                "✅ WIN",
                key=f"win_{bet['id']}",
                use_container_width=True
            ):

                settle_bet(
                    bet["id"],
                    "Win",
                    bet["stake"],
                    bet["market_odds"]
                )

                st.rerun()


        with loss_col:

            if st.button(
                "❌ LOSS",
                key=f"loss_{bet['id']}",
                use_container_width=True
            ):

                settle_bet(
                    bet["id"],
                    "Loss",
                    bet["stake"],
                    bet["market_odds"]
                )

                st.rerun()


        with void_col:

            if st.button(
                "↩️ PUSH / VOID",
                key=f"void_{bet['id']}",
                use_container_width=True
            ):

                settle_bet(
                    bet["id"],
                    "Void",
                    bet["stake"],
                    bet["market_odds"]
                )

                st.rerun()


        # ==================================
        # CASHOUT
        # ==================================

        with st.expander(
            "💰 Cash Out"
        ):

            cashout_return = (
                st.number_input(
                    "Cashout Return",
                    min_value=0.00,
                    value=float(
                        bet["stake"]
                    ),
                    step=0.50,
                    format="%.2f",
                    key=(
                        f"cashout_return_"
                        f"{bet['id']}"
                    )
                )
            )


            cashout_profit = (
                float(cashout_return)
                - float(bet["stake"])
            )


            st.caption(
                f"Cashout P/L: "
                f"{cashout_profit:+.2f}"
            )


            if st.button(
                "💰 CONFIRM CASH OUT",
                key=f"cashout_{bet['id']}",
                use_container_width=True,
                type="primary"
            ):

                try:

                    settle_cashout(
                        bet["id"],
                        bet["stake"],
                        cashout_return
                    )

                    st.rerun()


                except Exception as e:

                    st.error(
                        f"Could not cash out "
                        f"bet: {e}"
                    )


def pending_bets_page():

    bets = load_pending_bets()


    regular_bets = [
        bet
        for bet in bets
        if bet["scope"]
        != "OUTRIGHT"
    ]


    outright_bets = [
        bet
        for bet in bets
        if bet["scope"]
        == "OUTRIGHT"
    ]


    st.header(
        f"⏳ Pending Bets "
        f"({len(bets)})"
    )


    if not bets:

        st.success(
            "No pending bets 🎉"
        )

        return


    tipsters = load_tipsters()


    tipster_map = {
        t["id"]:
            t["name"]
        for t in tipsters
    }


    regular_tab, outright_tab = (
        st.tabs([
            (
                f"🏀 Regular "
                f"({len(regular_bets)})"
            ),
            (
                f"🏆 Outrights "
                f"({len(outright_bets)})"
            )
        ])
    )


    with regular_tab:

        render_pending_group(
            regular_bets,
            tipster_map
        )


    with outright_tab:

        render_pending_group(
            outright_bets,
            tipster_map
        )


# ==========================================
# HISTORY
# ==========================================

def history_page():

    st.header(
        "📜 Bet History"
    )


    history = load_history_bets()


    if not history:

        st.info(
            "No settled bets yet."
        )

        return


    sports = sorted(
        list(
            set(
                (
                    bet.get("sport")
                    or DEFAULT_SPORT
                )
                for bet in history
            )
        )
    )


    col1, col2 = st.columns(2)


    with col1:

        sport_filter = st.selectbox(
            "Sport",
            ["All"] + sports,
            key="history_sport"
        )


    with col2:

        result_filter = st.selectbox(
            "Result",
            [
                "All",
                "Win",
                "Loss",
                "Cashout",
                "Void"
            ],
            key="history_result"
        )


    timing_filter = st.selectbox(
        "Bet Timing",
        [
            "All",
            "Pre-live",
            "Live"
        ],
        key="history_timing"
    )


    scope_source = [
        bet
        for bet in history
        if (
            sport_filter == "All"
            or (
                bet.get("sport")
                or DEFAULT_SPORT
            )
            == sport_filter
        )
    ]


    scopes = sorted(
        list(
            set(
                bet["scope"]
                for bet in scope_source
                if bet.get("scope")
            )
        )
    )


    scope_filter = st.selectbox(
        "Bet Type",
        ["All"] + scopes,
        key="history_scope"
    )


    league_source = [
        bet
        for bet in scope_source
        if (
            scope_filter == "All"
            or bet["scope"]
            == scope_filter
        )
    ]


    leagues = sorted(
        list(
            set(
                bet["league"]
                for bet in league_source
                if bet["league"]
            )
        )
    )


    col1, col2 = st.columns(2)


    with col1:

        league_filter = st.selectbox(
            "League",
            ["All"] + leagues,
            key="history_league"
        )


    with col2:

        origin_filter = st.selectbox(
            "Origin",
            [
                "All",
                "SELF",
                "TIPSTER"
            ],
            key="history_origin"
        )


    filtered = history.copy()


    if sport_filter != "All":

        filtered = [
            bet
            for bet in filtered
            if (
                bet.get("sport")
                or DEFAULT_SPORT
            )
            == sport_filter
        ]


    if scope_filter != "All":

        filtered = [
            bet
            for bet in filtered
            if bet["scope"]
            == scope_filter
        ]


    if result_filter != "All":

        filtered = [
            bet
            for bet in filtered
            if bet["result"]
            == result_filter
        ]


    if league_filter != "All":

        filtered = [
            bet
            for bet in filtered
            if bet["league"]
            == league_filter
        ]


    if origin_filter != "All":

        filtered = [
            bet
            for bet in filtered
            if bet["origin"]
            == origin_filter
        ]


    if timing_filter == "Live":

        filtered = [
            bet
            for bet in filtered
            if bool(
                bet.get("is_live", False)
            )
        ]


    elif timing_filter == "Pre-live":

        filtered = [
            bet
            for bet in filtered
            if not bool(
                bet.get("is_live", False)
            )
        ]


    performance = [
        bet
        for bet in filtered
        if bet["result"]
        in [
            "Win",
            "Loss",
            "Cashout"
        ]
    ]


    total_profit = sum(
        float(
            bet["profit"]
            or 0
        )
        for bet in performance
    )


    total_stake = sum(
        float(
            bet["stake"]
            or 0
        )
        for bet in performance
    )


    roi = (
        total_profit
        / total_stake
        * 100
        if total_stake
        else 0
    )


    c1, c2, c3, c4 = (
        st.columns(4)
    )


    with c1:

        st.metric(
            "Bets",
            len(filtered)
        )


    with c2:

        st.metric(
            "Stake",
            f"{total_stake:.2f}"
        )


    with c3:

        st.metric(
            "Profit",
            f"{total_profit:+.2f}"
        )


    with c4:

        st.metric(
            "ROI",
            f"{roi:+.2f}%"
        )


    rows = []


    for bet in filtered:

        selection = (
            format_bet_selection(
                bet
            )
        )


        if bet["scope"] == "OUTRIGHT":

            subject_display = (
                selection
            )

        elif bet["scope"] == "MATCH":

            subject_display = (
                bet["event"]
            )

        else:

            subject_display = (
                bet["subject"]
            )


        rows.append({

            "Date":
                bet["bet_date"],

            "Sport":
                (
                    bet.get("sport")
                    or DEFAULT_SPORT
                ),

            "Timing":
                (
                    "Live"
                    if bool(
                        bet.get(
                            "is_live",
                            False
                        )
                    )
                    else "Pre-live"
                ),

            "League":
                bet["league"],

            "Type":
                bet["scope"],

            "Event / Competition":
                bet["event"],

            "Subject / Selection":
                subject_display,

            "Market":
                bet["market"],

            "Selection":
                (
                    selection
                    if bet["scope"]
                    != "OUTRIGHT"
                    else ""
                ),

            "Odds":
                float(
                    bet["market_odds"]
                ),

            "Stake":
                float(
                    bet["stake"]
                ),

            "Origin":
                bet["origin"],

            "Confidence":
                bet["confidence"],

            "Result":
                bet["result"],

            "Cashout Return":
                (
                    float(
                        bet[
                            "cashout_return"
                        ]
                    )
                    if bet.get(
                        "cashout_return"
                    ) is not None
                    else None
                ),

            "Profit":
                float(
                    bet["profit"]
                )
        })


    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True
    )


# ==========================================
# MANAGE / EDIT
# ==========================================

def manage_bets_page():

    st.header(
        "✏️ Manage Bets"
    )


    bets = load_active_bets()


    if not bets:

        st.info(
            "No active bets."
        )

        return


    label_map = {}


    for bet in bets:

        if bet["scope"] == "OUTRIGHT":

            description = (
                format_bet_selection(
                    bet
                )
            )

            label = (
                f"{bet['bet_date']} | "
                f"🏆 {bet['event']} | "
                f"{bet['market']} | "
                f"{description} | "
                f"@{float(bet['market_odds']):.2f} | "
                f"{bet['result']}"
            )


        else:

            subject = (
                bet["event"]
                if bet["scope"] == "MATCH"
                else bet["subject"]
            )


            selection = (
                format_bet_selection(
                    bet
                )
            )


            label = (
                f"{bet['bet_date']} | "
                f"{subject} | "
                f"{bet['market']} "
                f"{selection} | "
                f"@{float(bet['market_odds']):.2f} | "
                f"{bet['result']}"
            )


        label_map[label] = bet


    selected_label = (
        st.selectbox(
            "Choose Bet",
            list(
                label_map.keys()
            )
        )
    )


    bet = label_map[
        selected_label
    ]


    bet_id = bet["id"]

    edit_sport = (
        bet.get("sport")
        or DEFAULT_SPORT
    )


    st.divider()

    st.caption(
        f"Sport: {edit_sport}"
    )

    st.subheader(
        "Edit Bet"
    )


    # ======================================
    # DATE / LEAGUE
    # ======================================

    col1, col2 = st.columns(2)


    with col1:

        edit_date = st.date_input(
            "Bet Date",
            value=datetime.strptime(
                bet["bet_date"],
                "%Y-%m-%d"
            ).date(),
            key=f"edit_date_{bet_id}"
        )


    with col2:

        edit_league_options = (
            load_user_league_options(
                edit_sport
            )
        )

        if (
            bet["league"]
            not in edit_league_options
        ):
            edit_league_options.append(
                bet["league"]
            )

        edit_league = st.selectbox(
            "League / Tour",
            edit_league_options,
            index=safe_index(
                edit_league_options,
                bet["league"]
            ),
            accept_new_options=True,
            key=f"edit_league_{bet_id}"
        )


    edit_is_live = st.checkbox(
        "🔴 Live Bet",
        value=bool(
            bet.get("is_live", False)
        ),
        key=f"edit_is_live_{bet_id}"
    )


    scope_options = (
        get_scope_options(
            edit_sport
        )
    )


    edit_scope = st.radio(
        "Bet Type",
        scope_options,
        index=safe_index(
            scope_options,
            bet["scope"]
        ),
        horizontal=True,
        key=f"edit_scope_{bet_id}"
    )


    edit_event = st.text_input(
        (
            "Competition / Event"
            if edit_scope
            == "OUTRIGHT"
            else "Event"
        ),
        value=bet["event"] or "",
        key=f"edit_event_{bet_id}"
    )


    edit_subject = None
    edit_selection_2 = None
    edit_line = None
    edit_side = None


    # ======================================
    # OUTRIGHT
    # ======================================

    if edit_scope == "OUTRIGHT":

        edit_market_options = (
            load_user_market_options(
                edit_sport,
                "OUTRIGHT"
            )
        )

        if (
            bet["market"]
            not in edit_market_options
        ):
            edit_market_options.append(
                bet["market"]
            )

        edit_market = st.selectbox(
            "Outright Market",
            edit_market_options,
            index=safe_index(
                edit_market_options,
                bet["market"]
            ),
            accept_new_options=True,
            key=f"edit_market_{bet_id}"
        )


        label_1, label_2 = (
            outright_selection_labels(
                edit_market,
                edit_sport
            )
        )


        edit_subject = (
            st.text_input(
                label_1,
                value=(
                    bet["subject"]
                    or ""
                ),
                key=(
                    f"edit_subject_"
                    f"{bet_id}"
                )
            )
        )


        if label_2:

            edit_selection_2 = (
                st.text_input(
                    label_2,
                    value=(
                        bet.get(
                            "selection_2"
                        )
                        or ""
                    ),
                    key=(
                        f"edit_selection2_"
                        f"{bet_id}"
                    )
                )
            )


        edit_period = (
            "Full Competition"
        )


    # ======================================
    # REGULAR
    # ======================================

    else:

        if edit_scope == "PLAYER":

            edit_subject = (
                st.text_input(
                    "Player",
                    value=(
                        bet["subject"]
                        or ""
                    ),
                    key=(
                        f"edit_player_"
                        f"{bet_id}"
                    )
                )
            )


        elif edit_scope == "TEAM":

            edit_subject = (
                st.text_input(
                    "Team",
                    value=(
                        bet["subject"]
                        or ""
                    ),
                    key=(
                        f"edit_team_"
                        f"{bet_id}"
                    )
                )
            )


        edit_market_options = (
            load_user_market_options(
                edit_sport,
                edit_scope
            )
        )

        if (
            bet["market"]
            not in edit_market_options
        ):
            edit_market_options.append(
                bet["market"]
            )


        edit_market = st.selectbox(
            "Market",
            edit_market_options,
            index=safe_index(
                edit_market_options,
                bet["market"]
            ),
            accept_new_options=True,
            key=f"edit_market_{bet_id}"
        )


        edit_period_options = (
            get_periods(
                edit_sport
            )
        )

        if (
            bet["period"]
            and bet["period"]
            not in edit_period_options
        ):
            edit_period_options.append(
                bet["period"]
            )


        edit_period = st.selectbox(
            "Period",
            edit_period_options,
            index=safe_index(
                edit_period_options,
                bet["period"]
            ),
            key=f"edit_period_{bet_id}"
        )


        default_edit_markets = (
            get_default_markets(
                edit_sport,
                edit_scope
            )
        )


        if (
            edit_market
            in default_edit_markets
        ):

            edit_market_style = (
                get_market_style(
                    edit_sport,
                    edit_scope,
                    edit_market
                )
            )

        else:

            edit_market_style = (
                infer_saved_custom_market_format(
                    edit_sport,
                    edit_scope,
                    edit_market
                )
            )

            edit_market_style = {
                "Over / Under":
                    "total",
                "Winner / Selection":
                    "winner",
                "Handicap / Spread":
                    "handicap",
                "Yes / No":
                    "yes_no"
            }.get(
                edit_market_style,
                "total"
            )


        if edit_market_style == "winner":

            side_options = (
                get_winner_side_options(
                    edit_sport,
                    edit_market
                )
            )


            edit_side = st.radio(
                "Selection",
                side_options,
                index=safe_index(
                    side_options,
                    bet["side"]
                ),
                horizontal=True,
                key=f"edit_side_{bet_id}"
            )


        elif edit_market_style == "handicap":

            side_options = (
                get_winner_side_options(
                    edit_sport,
                    edit_market
                )
            )


            edit_side = st.radio(
                "Selection",
                side_options,
                index=safe_index(
                    side_options,
                    bet["side"]
                ),
                horizontal=True,
                key=f"edit_side_{bet_id}"
            )


            edit_line = (
                st.number_input(
                    "Line",
                    value=float(
                        bet["line"]
                        or 0
                    ),
                    step=0.5,
                    format="%.1f",
                    key=(
                        f"edit_line_"
                        f"{bet_id}"
                    )
                )
            )


        elif edit_market_style == "yes_no":

            side_options = [
                "Yes",
                "No"
            ]


            edit_side = st.radio(
                "Selection",
                side_options,
                index=safe_index(
                    side_options,
                    bet["side"]
                ),
                horizontal=True,
                key=f"edit_side_{bet_id}"
            )


        else:

            side_options = [
                "Over",
                "Under"
            ]


            edit_side = st.radio(
                "Side",
                side_options,
                index=safe_index(
                    side_options,
                    bet["side"]
                ),
                horizontal=True,
                key=f"edit_side_{bet_id}"
            )


            edit_line = (
                st.number_input(
                    "Line",
                    value=float(
                        bet["line"]
                        or 0
                    ),
                    step=0.5,
                    format="%.1f",
                    key=(
                        f"edit_line_"
                        f"{bet_id}"
                    )
                )
            )


    # ======================================
    # BOOK / ODDS
    # ======================================

    col1, col2 = st.columns(2)


    with col1:

        edit_bookmaker = (
            st.selectbox(
                "Bookmaker",
                BOOKMAKERS,
                index=safe_index(
                    BOOKMAKERS,
                    bet["bookmaker"]
                ),
                key=f"edit_book_{bet_id}"
            )
        )


    with col2:

        edit_market_odds = (
            st.number_input(
                "Odds Taken",
                min_value=1.01,
                value=float(
                    bet["market_odds"]
                ),
                step=0.01,
                format="%.2f",
                key=f"edit_odds_{bet_id}"
            )
        )


    # ======================================
    # ORIGIN
    # ======================================

    origin_options = [
        "SELF",
        "TIPSTER"
    ]


    edit_origin = st.radio(
        "Origin",
        origin_options,
        index=safe_index(
            origin_options,
            bet["origin"]
        ),
        horizontal=True,
        key=f"edit_origin_{bet_id}"
    )


    edit_my_odds = None
    edit_tipster_id = None
    edit_tipster_posted_odds = None
    edit_has_reasoning = False
    edit_primary = None
    edit_secondary = None

    edit_reasons = (
        get_reasons(
            edit_sport
        )
    )


    if edit_origin == "SELF":

        edit_my_odds = (
            st.number_input(
                "My Fair Odds",
                min_value=1.01,
                value=float(
                    bet["my_odds"]
                    or 1.80
                ),
                step=0.01,
                format="%.2f",
                key=(
                    f"edit_myodds_"
                    f"{bet_id}"
                )
            )
        )


        confidence_options = [
            "Low",
            "Medium",
            "High"
        ]


        edit_confidence = (
            st.radio(
                "Confidence",
                confidence_options,
                index=safe_index(
                    confidence_options,
                    bet["confidence"],
                    1
                ),
                horizontal=True,
                key=f"edit_conf_{bet_id}"
            )
        )


        reason_options = (
            ["Select reason..."]
            + edit_reasons
        )


        edit_primary = (
            st.selectbox(
                "Primary Reason",
                reason_options,
                index=safe_index(
                    reason_options,
                    bet["primary_reason"]
                ),
                key=(
                    f"edit_primary_"
                    f"{bet_id}"
                )
            )
        )


        secondary_options = (
            ["None"]
            + [
                reason
                for reason in edit_reasons
                if reason
                != edit_primary
            ]
        )


        edit_secondary = (
            st.selectbox(
                "Secondary Reason",
                secondary_options,
                index=safe_index(
                    secondary_options,
                    (
                        bet[
                            "secondary_reason"
                        ]
                        or "None"
                    )
                ),
                key=(
                    f"edit_secondary_"
                    f"{bet_id}"
                )
            )
        )


        edit_has_reasoning = True


    else:

        tipsters = load_tipsters()


        if not tipsters:

            st.warning(
                "No tipsters saved."
            )

            edit_tipster_id = None


        else:

            tipster_names = [
                t["name"]
                for t in tipsters
            ]


            tipster_ids = {
                t["name"]:
                    t["id"]
                for t in tipsters
            }


            current_tipster = None


            for tipster in tipsters:

                if (
                    tipster["id"]
                    == bet["tipster_id"]
                ):

                    current_tipster = (
                        tipster["name"]
                    )


            selected_tipster = (
                st.selectbox(
                    "Tipster",
                    tipster_names,
                    index=safe_index(
                        tipster_names,
                        current_tipster
                    ),
                    key=(
                        f"edit_tipster_"
                        f"{bet_id}"
                    )
                )
            )


            edit_tipster_id = (
                tipster_ids[
                    selected_tipster
                ]
            )


        has_posted = (
            bet[
                "tipster_posted_odds"
            ]
            is not None
        )


        edit_has_posted = (
            st.checkbox(
                "I know the tipster's "
                "posted odds",
                value=has_posted,
                key=(
                    f"edit_hasposted_"
                    f"{bet_id}"
                )
            )
        )


        if edit_has_posted:

            edit_tipster_posted_odds = (
                st.number_input(
                    "Tipster Posted Odds",
                    min_value=1.01,
                    value=float(
                        bet[
                            "tipster_posted_odds"
                        ]
                        or 1.90
                    ),
                    step=0.01,
                    format="%.2f",
                    key=(
                        f"edit_posted_"
                        f"{bet_id}"
                    )
                )
            )


        confidence_options = [
            "N/A",
            "Low",
            "Medium",
            "High"
        ]


        edit_confidence = (
            st.radio(
                "Your Confidence",
                confidence_options,
                index=safe_index(
                    confidence_options,
                    bet["confidence"]
                ),
                horizontal=True,
                key=f"edit_conf_{bet_id}"
            )
        )


        edit_has_reasoning = (
            st.checkbox(
                "I also have my own "
                "reasoning for this bet",
                value=bool(
                    bet[
                        "has_own_reasoning"
                    ]
                ),
                key=(
                    f"edit_reasoning_"
                    f"{bet_id}"
                )
            )
        )


        if edit_has_reasoning:

            reason_options = (
                ["Select reason..."]
                + edit_reasons
            )


            edit_primary = (
                st.selectbox(
                    "Primary Reason",
                    reason_options,
                    index=safe_index(
                        reason_options,
                        bet[
                            "primary_reason"
                        ]
                    ),
                    key=(
                        f"edit_primary_"
                        f"{bet_id}"
                    )
                )
            )


            secondary_options = (
                ["None"]
                + [
                    reason
                    for reason in edit_reasons
                    if reason
                    != edit_primary
                ]
            )


            edit_secondary = (
                st.selectbox(
                    "Secondary Reason",
                    secondary_options,
                    index=safe_index(
                        secondary_options,
                        (
                            bet[
                                "secondary_reason"
                            ]
                            or "None"
                        )
                    ),
                    key=(
                        f"edit_secondary_"
                        f"{bet_id}"
                    )
                )
            )


    # ======================================
    # STAKE / RESULT
    # ======================================

    edit_stake = st.number_input(
        "Stake",
        min_value=0.01,
        value=float(
            bet["stake"]
        ),
        step=1.00,
        key=f"edit_stake_{bet_id}"
    )


    result_options = [
        "Pending",
        "Win",
        "Loss",
        "Cashout",
        "Void"
    ]


    edit_result = st.selectbox(
        "Result",
        result_options,
        index=safe_index(
            result_options,
            bet["result"]
        ),
        key=f"edit_result_{bet_id}"
    )


    edit_cashout_return = None


    if edit_result == "Cashout":

        edit_cashout_return = (
            st.number_input(
                "Cashout Return",
                min_value=0.00,
                value=float(
                    bet[
                        "cashout_return"
                    ]
                    if bet.get(
                        "cashout_return"
                    ) is not None
                    else bet["stake"]
                ),
                step=0.50,
                format="%.2f",
                key=(
                    f"edit_cashout_"
                    f"{bet_id}"
                )
            )
        )


        st.caption(
            f"Cashout P/L: "
            f"{float(edit_cashout_return) - float(edit_stake):+.2f}"
        )


    edit_notes = st.text_area(
        "Notes",
        value=bet["notes"] or "",
        key=f"edit_notes_{bet_id}"
    )


    # ======================================
    # SAVE CHANGES
    # ======================================

    if st.button(
        "💾 SAVE CHANGES",
        type="primary",
        use_container_width=True,
        key=f"save_edit_{bet_id}"
    ):


        if not edit_event.strip():

            st.error(
                "Event / Competition "
                "is required."
            )

            return


        if (
            edit_scope
            in [
                "PLAYER",
                "TEAM",
                "OUTRIGHT"
            ]
            and not (
                edit_subject
                and edit_subject.strip()
            )
        ):

            st.error(
                "Selection is required."
            )

            return


        if (
            edit_scope == "OUTRIGHT"
            and outright_needs_second_selection(
                edit_market,
                edit_sport
            )
            and not (
                edit_selection_2
                and edit_selection_2.strip()
            )
        ):

            st.error(
                "Second selection "
                "is required."
            )

            return


        if (
            edit_origin == "SELF"
            and edit_primary
            == "Select reason..."
        ):

            st.error(
                "Select a Primary Reason."
            )

            return


        if (
            edit_origin == "TIPSTER"
            and edit_tipster_id is None
        ):

            st.error(
                "Select a valid tipster."
            )

            return


        if (
            edit_origin == "TIPSTER"
            and edit_has_reasoning
            and edit_primary
            == "Select reason..."
        ):

            st.error(
                "Select a Primary Reason."
            )

            return


        metrics = calculate_metrics(
            edit_market_odds,
            edit_my_odds,
            edit_tipster_posted_odds
        )


        if edit_result == "Cashout":

            edit_profit = round(
                float(
                    edit_cashout_return
                )
                - float(edit_stake),
                2
            )

        else:

            edit_profit = (
                calculate_profit(
                    edit_result,
                    edit_stake,
                    edit_market_odds
                )
            )


        if edit_result == "Pending":

            new_settled_at = None
            new_cashout_at = None


        else:

            new_settled_at = (
                bet["settled_at"]
                or now_utc()
            )


            if (
                edit_result
                == "Cashout"
            ):

                new_cashout_at = (
                    bet.get(
                        "cashout_at"
                    )
                    or now_utc()
                )

            else:

                new_cashout_at = None


        update_record = {

            "sport":
                edit_sport,

            "is_live":
                bool(edit_is_live),

            "bet_date":
                edit_date.isoformat(),

            "league":
                edit_league,

            "event":
                edit_event.strip(),

            "scope":
                edit_scope,

            "subject":
                (
                    edit_subject.strip()
                    if edit_subject
                    else None
                ),

            "selection_2":
                (
                    edit_selection_2.strip()
                    if edit_selection_2
                    else None
                ),

            "market":
                edit_market,

            "period":
                edit_period,

            "side":
                edit_side,

            "line":
                edit_line,

            "bookmaker":
                edit_bookmaker,

            "market_odds":
                edit_market_odds,

            "my_odds":
                edit_my_odds,

            "origin":
                edit_origin,

            "tipster_id":
                edit_tipster_id,

            "tipster_posted_odds":
                edit_tipster_posted_odds,

            "confidence":
                edit_confidence,

            "has_own_reasoning":
                edit_has_reasoning,

            "primary_reason":
                (
                    None
                    if edit_primary
                    == "Select reason..."
                    else edit_primary
                ),

            "secondary_reason":
                (
                    None
                    if edit_secondary
                    in [
                        None,
                        "None"
                    ]
                    else edit_secondary
                ),

            "stake":
                edit_stake,

            "result":
                edit_result,

            "settled_at":
                new_settled_at,

            "cashout_return":
                (
                    edit_cashout_return
                    if edit_result
                    == "Cashout"
                    else None
                ),

            "cashout_at":
                new_cashout_at,

            "p_market":
                metrics["p_market"],

            "p_you":
                metrics["p_you"],

            "edge_pp":
                metrics["edge_pp"],

            "ev_pct":
                metrics["ev_pct"],

            "price_deterioration_pp":
                metrics[
                    "price_deterioration_pp"
                ],

            "profit":
                edit_profit,

            "notes":
                (
                    edit_notes.strip()
                    if edit_notes.strip()
                    else None
                ),

            "updated_at":
                now_utc()
        }


        try:

            (
                supabase
                .table("bets")
                .update(
                    update_record
                )
                .eq(
                    "id",
                    bet_id
                )
                .eq(
                    "user_id",
                    st.session_state.user_id
                )
                .execute()
            )


            st.success(
                "✅ Bet updated successfully."
            )

            st.rerun()


        except Exception as e:

            st.error(
                f"Could not update bet: {e}"
            )


    # ======================================
    # SOFT DELETE
    # ======================================

    st.divider()

    st.subheader(
        "Delete Bet"
    )


    st.caption(
        "The bet will move to Trash. "
        "It will not be permanently deleted."
    )


    if (
        st.session_state.delete_confirm_id
        != bet_id
    ):

        if st.button(
            "🗑️ MOVE TO TRASH",
            use_container_width=True,
            key=f"delete_{bet_id}"
        ):

            st.session_state.delete_confirm_id = (
                bet_id
            )

            st.rerun()


    else:

        st.warning(
            "Are you sure you want "
            "to move this bet to Trash?"
        )


        c1, c2 = st.columns(2)


        with c1:

            if st.button(
                "Cancel",
                use_container_width=True,
                key=(
                    f"cancel_delete_"
                    f"{bet_id}"
                )
            ):

                st.session_state.delete_confirm_id = (
                    None
                )

                st.rerun()


        with c2:

            if st.button(
                "Yes, move to Trash",
                type="primary",
                use_container_width=True,
                key=(
                    f"confirm_delete_"
                    f"{bet_id}"
                )
            ):

                try:

                    soft_delete_bet(
                        bet_id
                    )

                    st.session_state.delete_confirm_id = (
                        None
                    )

                    st.rerun()


                except Exception as e:

                    st.error(
                        f"Could not delete "
                        f"bet: {e}"
                    )


# ==========================================
# TRASH
# ==========================================

def trash_page():

    deleted = (
        load_deleted_bets()
    )


    st.header(
        f"🗑️ Trash ({len(deleted)})"
    )


    st.caption(
        "Deleted bets are excluded from "
        "counters, History and Analysis."
    )


    if not deleted:

        st.success(
            "Trash is empty."
        )

        return


    for bet in deleted:

        st.divider()


        subject = (

            bet["event"]

            if bet["scope"] == "MATCH"

            else bet["subject"]
        )


        st.subheader(
            subject
        )


        market_text = (
            f"{bet['market']} | "
            f"{bet['side']}"
        )


        if bet["line"] is not None:

            market_text += (
                f" {float(bet['line']):g}"
            )


        st.write(
            market_text
        )


        st.caption(
            f"{bet.get('sport') or DEFAULT_SPORT} | "
            f"{bet['league']} | "
            f"Odds {float(bet['market_odds']):.2f} | "
            f"Result: {bet['result']}"
        )


        st.caption(
            f"Deleted: "
            f"{bet['deleted_at'] or 'Unknown'}"
        )


        if st.button(
            "♻️ RESTORE",
            key=f"restore_{bet['id']}",
            use_container_width=True
        ):

            try:

                restore_bet(
                    bet["id"]
                )

                st.rerun()


            except Exception as e:

                st.error(
                    f"Could not restore bet: {e}"
                )


# ==========================================
# MAIN
# ==========================================

if not st.session_state.logged_in:

    login_page()

    st.stop()


# ==========================================
# SIDEBAR
# ==========================================

with st.sidebar:

    st.write(
        f"👤 "
        f"{st.session_state.user_email}"
    )


    if st.button(
        "Logout",
        use_container_width=True
    ):

        logout()


# ==========================================
# HEADER
# ==========================================

st.title(
    "🎯 Bet Tracker"
)

st.caption(
    "Personal betting & analytics tracker"
)


# ==========================================
# COUNTERS
# ==========================================

try:

    total_bets = (
        get_total_bets_count()
    )

    pending_count = (
        get_pending_bets_count()
    )

    settled_count = (
        get_settled_bets_count()
    )


    c1, c2, c3 = st.columns(3)


    with c1:

        st.metric(
            "Total Bets",
            total_bets
        )


    with c2:

        st.metric(
            "Pending",
            pending_count
        )


    with c3:

        st.metric(
            "Settled",
            settled_count
        )


except Exception as e:

    st.warning(
        f"Could not load counters: {e}"
    )



# ==========================================
# NAVIGATION
# ==========================================

(
    add_tab,
    pending_tab,
    history_tab,
    analysis_tab,
    suggestions_tab,
    manage_tab,
    trash_tab
) = st.tabs([

    "➕ Add Bet",
    "⏳ Pending",
    "📜 History",
    "📊 Analysis",
    "💡 Suggestions",
    "✏️ Manage",
    "🗑️ Trash"
])


with add_tab:

    add_bet_page()


with pending_tab:

    pending_bets_page()


with history_tab:

    history_page()


with analysis_tab:

    analysis_page(
        supabase,
        load_tipsters
    )


with suggestions_tab:

    suggestions_page(
        supabase,
        load_tipsters
    )


with manage_tab:

    manage_bets_page()


with trash_tab:

    trash_page()
