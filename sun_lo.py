# Sunpos - low res
# 221021

import math
import time


def sunpos(when, where, refract):

    # Extract the passed data
    ye, mo, da, ho, mi, se, timezone = when
    latitude, longitude = where

    # Trig constants
    tau = math.pi * 2
    rpd = math.pi / 180

    # Latitude/longitude in radians
    rlat = latitude * rpd
    rlon = longitude * rpd

    # Decimal hour of the day at Greenwich
    utim = ho - timezone + mi / 60 + se / 3600

    # Days from J2000, accurate only from 1901 to 2099
    dnum = (
        367 * ye
        - 7 * (ye + (mo + 9) // 12) // 4
        + 275 * mo // 9
        + da
        - 730531.5
        + utim / 24
    )

    # Mean longitude of the sun
    slon = rnge(dnum * 0.01720279239 + 4.894967873, 0, tau)

    # Mean anomaly of the Sun
    sano = rnge(dnum * 0.01720197034 + 6.240040768, 0, tau)

    # Ecliptic longitude of the sun
    ecli = slon + 0.03342305518 * math.sin(sano) + 0.0003490658504 * math.sin(2 * sano)

    # Obliquity of the ecliptic
    obli = 0.4090877234 - 0.000000006981317008 * dnum

    # Right ascension of the sun
    rasc = math.atan2(math.cos(obli) * math.sin(ecli), math.cos(ecli))

    # Declination of the sun
    decl = math.asin(math.sin(obli) * math.sin(ecli))

    # Local sidereal time
    stim = rnge(4.894961213 + 6.300388099 * dnum + rlon, 0, tau)

    # Hour angle of the sun
    hang = rnge(stim - rasc, 0, tau)

    # Local elevation of the sun
    elevation = math.asin(
        math.sin(decl) * math.sin(rlat)
        + math.cos(decl) * math.cos(rlat) * math.cos(hang)
    )

    # Local azimuth of the sun
    azimuth = math.atan2(
        -math.cos(decl) * math.cos(rlat) * math.sin(hang),
        math.sin(decl) - math.sin(rlat) * math.sin(elevation),
    )

    # Convert azimuth and elevation to degrees
    azimuth = rnge(azimuth / rpd, 0, 360)
    elevation = rnge(elevation / rpd, -180, 180)

    # Refraction correction
    if refract:
        targ = (elevation + (10.3 / (elevation + 5.11))) * rpd
        refraction = (1.02 / math.tan(targ)) / 60
        elevation += refraction

    # Return azimuth, elevation, and refraction
    return [azimuth, elevation]


def rnge(x, rmin, rmax):
    shiftedx = x - rmin
    delta = rmax - rmin
    return (((shiftedx % delta) + delta) % delta) + rmin


if __name__ == "__main__":

    # Sandia Labs example
    when = [1981, 6, 21, 8, 0, 0, -7]
    where = [34.9622313889, -106.509031111]
    refract = True
    azimuth, elevation = sunpos(when, where, refract)
    print("\nSun position lower precision")
    print("When: ", when)
    print("Where: ", where)
    print("Refraction: ", refract)
    print("Azimuth: ", azimuth)
    print("Elevation: ", elevation)
