import gzip
import xml.etree.ElementTree as ET

path = r"P:\download\Copied_3571\Copied_3571\3571.prproj"

with gzip.open(path, "rb") as f:
    xml_data = f.read().decode("utf-8")

#save to xml file
with open("output.xml", "w", encoding="utf-8") as f:
    f.write(xml_data)

root = ET.fromstring(xml_data)
