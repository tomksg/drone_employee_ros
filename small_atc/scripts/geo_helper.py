#!/usr/bin/env python2
import rospy, math
from geometry_msgs.msg import Point, PoseStamped
from sensor_msgs.msg import NavSatFix
from small_atc_msgs.msg import *
from nav_msgs.msg import Path
from threading import Thread

RADIUS_OF_EARTH = 6371.0 * 1000 # meters 

###
# Map metadata loader
class Origin(object):
    def __init__(self, latitude, longitude, altitude):
        self._latitude = latitude
        self._longitude = longitude
        self._altitude = altitude

    def latitude(self):
        return self._latitude

    def longitude(self):
        return self._longitude

    def altitude(self):
        return self._altitude

class MapMeta(object):

    def __init__(self):
        origin_lat = rospy.get_param("~origin_latitude")
        origin_lon = rospy.get_param("~origin_longitude")
        origin_alt = rospy.get_param("~origin_altitude")
        self._origin = Origin(origin_lat, origin_lon, origin_alt)

    def origin(self):
        return self._origin

meta = object()

payed_address = set()

def grad2len(grad):
    return math.pi * RADIUS_OF_EARTH * grad / 180

def len2grad(len):
    return len * 180 / math.pi / RADIUS_OF_EARTH

def satFix2Point(fix):
    pt = Point()
    pt.x = grad2len(fix.longitude - meta.origin().longitude())
    pt.y = grad2len(fix.latitude  - meta.origin().latitude())
    pt.z = (fix.altitude - meta.origin().altitude())
    return pt

def point2SatFix(pt):
    fix = SatFix()
    fix.latitude  = meta.origin().latitude()  + len2grad(pt.y)
    fix.longitude = meta.origin().longitude() + len2grad(pt.x)
    fix.altitude  = meta.origin().altitude()  + pt.z
    return fix

def navSatFix2Pose(fix):
    p = PoseStamped()
    p.header.frame_id = "map"
    p.pose.position = satFix2Point(fix)
    return p

def connect(topic_in, topic_out, handler):
    pub = rospy.Publisher(topic_out[0], topic_out[1], queue_size=1)
    def _handler(msg):
        try:
            pub.publish(handler(msg))
        except Exception as e:
            rospy.logerr("Exception: " + str(e))
    rospy.Subscriber(topic_in[0], topic_in[1], _handler)

def requestHandler(msg):
    # Payment check
    #if (not msg.sender in payed_address):
    #    raise Exception("Address (" + msg.sender.data.data + ") is not payed!")
    #else:
    #    payed_address.remove(msg.sender)
    # Geo conversions
    req = LocalRouteRequest()
    req.id = msg.id
    req.checkpoints = map(satFix2Point, msg.checkpoints)
    return req

def responseHandler(msg):
    res = RouteResponse()
    res.valid = msg.valid
    res.id = msg.id
    res.route = map(point2SatFix, msg.route)
    # Path publish
    emitPath(msg.id, msg.route)
    return res

def emitPath(ident, pointList):
    pub = rospy.Publisher("path/"+str(ident), Path, queue_size=1) 
    path = Path()
    path.header.frame_id = "map"

    def point2ps(point):
        ps = PoseStamped()
        ps.header.frame_id = path.header.frame_id
        ps.pose.position = point
        return ps

    path.poses = [point2ps(p) for p in pointList]

    def path_publisher():
        while not rospy.is_shutdown():
            pub.publish(path)
            rospy.sleep(1)
    t = Thread(target=path_publisher)
    t.start()

if __name__ == '__main__':
    rospy.init_node("atc_geo_helper")
    meta = MapMeta()

    connect(("route/request", RouteRequest),
            ("route/request_local", LocalRouteRequest),
            requestHandler)
    connect(("route/response_local", LocalRouteResponse),
            ("route/response", RouteResponse),
            responseHandler)
    rospy.Subscriber("payed_address", Address, lambda msg: payed_address.add(msg.data))

# Drones visualisation hook
#    connect(("/dron_1/mavros/global_position/global", NavSatFix),
#            ("/dron_1/position", PoseStamped),
#            navSatFix2Pose)
#    connect(("/dron_2/mavros/global_position/global", NavSatFix),
#            ("/dron_2/position", PoseStamped),
#            navSatFix2Pose)
#    connect(("/dron_3/mavros/global_position/global", NavSatFix),
#            ("/dron_3/position", PoseStamped),
#            navSatFix2Pose)
    rospy.spin()
