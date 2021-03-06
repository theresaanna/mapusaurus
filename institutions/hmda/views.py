from django.db.models import Count
from django.http import HttpResponseBadRequest

from batch.conversions import use_GET_in
from hmda.models import HMDARecord


def volume_per_100_households(volume, num_households):
    """Volume of originations can be misleading. Normalize it to some degree
    by considering the number of houses in the same census tract."""
    if num_households:
        return volume * 100.0 / num_households
    else:
        return 0


def loan_originations(request_dict):
    """Get loan originations for a given lender, county combination. This
    ignores year for the moment."""

    state_fips = request_dict.get('state_fips', '')
    county_fips = request_dict.get('county_fips', '')
    lender = request_dict.get('lender', '')

    if state_fips and county_fips and lender:
        records = HMDARecord.objects.filter(
            countyfp=county_fips, lender=lender, statefp=state_fips,
            action_taken__lte=6)    # actions 7-8 are preapprovals to ignore
        query = records.values(
            'geoid', 'geoid__census2010households__total'
        ).annotate(volume=Count('geoid'))
        data = {}
        for row in query:
            data[row['geoid']] = {
                'volume': row['volume'],
                'num_households': row['geoid__census2010households__total'],
                'volume_per_100_households': volume_per_100_households(
                    row['volume'], row['geoid__census2010households__total'])
            }
        return data
    else:
        return HttpResponseBadRequest(
            "Missing one of state_fips, county_fips, lender")


def loan_originations_http(request):
    return use_GET_in(loan_originations, request)
