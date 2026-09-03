from ayon_core.pipeline import load
import ayon_harmony.api as harmony


_ensure_oh = """
if (typeof AyonHarmony === 'undefined') {
    var AYON_HARMONY_JS = System.getenv('AYON_HARMONY_JS') + '/AyonHarmony.js';
    include(AYON_HARMONY_JS.replace(/\\\\/g, "/"));
}
if (typeof $ === 'undefined') {
    $ = this.__proto__['$'];
}
"""

import_image = _ensure_oh + """
function import_image(args)
{
    var filepath = args[0];
    var layerName = args[1];

    var imageFile = new $.oFile(filepath);

    var element = $.scene.addElement(layerName, "TVG", 12, "BW");
    var col = $.scene.addColumn("DRAWING", layerName, element);
    element.column = col;

    var imgInfo = CELIO.getInformation(imageFile.path);
    var drawing;

    if (imgInfo && imgInfo.width && imgInfo.height) {
        var utransformBin = specialFolders.bin + "/utransform";
        var tempFolder = $.scn.tempFolder;
        var convertedPath = tempFolder.path + "/" + imageFile.name + ".tvg";
        var convertProcess = new $.oProcess(utransformBin, [
            "-outformat", "TVG", "-debug",
            "-resolution", imgInfo.width, imgInfo.height,
            "-outfile", convertedPath, imageFile.path
        ]);
        convertProcess.execute();

        var convertedFile = new $.oFile(convertedPath);
        if (convertedFile.exists) {
            drawing = element.addDrawing(1, 1, convertedPath, false);
        }
    }
    if (!drawing) {
        drawing = element.addDrawing(1, 1, imageFile.path, false);
    }

    var imageNode = $.scn.root.addDrawingNode(
        layerName, new $.oPoint(0, 0, 0), element
    );
    imageNode.alignment_rule = "ASIS";
    imageNode.attributes.drawing.element.setValue(drawing.name, 1);
    imageNode.attributes.drawing.element.column.extendExposures();

    // Le loader importe par defaut en "Vertical Fit". Pour retrouver la vraie taille de
    // l'image ("Actual Size"), le même facteur est appliqué sur les 2 axes du scale.
    var sceneResY = $.scene.resolutionY;
    if (imgInfo && imgInfo.height > 0 && sceneResY > 0) {
        var uniformScale = imgInfo.height / sceneResY;
        imageNode.scale.x = uniformScale;
        imageNode.scale.y = uniformScale;
    }

    node.getAttr(imageNode.path, 1, "lineArtDrawingMode").setValue("BitmapDrawingMode");
    node.getAttr(imageNode.path, 1, "applyMatteToColor").setValue(1); // 1 = Straight
    imageNode.use_drawing_pivot = "Apply Embedded Pivot on Drawing Layer";

    return imageNode.path;
}
import_image
"""

replace_image = _ensure_oh + """
function replace_image(args)
{
    var filepath = args[0];
    var oldNodePath = args[1];
    var layerName = args[2];

    var imageFile = new $.oFile(filepath);
    var element = $.scene.addElement(layerName, "TVG", 12, "BW");
    var col = $.scene.addColumn("DRAWING", layerName, element);
    element.column = col;

    var imgInfo = CELIO.getInformation(imageFile.path);
    var drawing;
    if (imgInfo && imgInfo.width && imgInfo.height) {
        var utransformBin = specialFolders.bin + "/utransform";
        var tempFolder = $.scn.tempFolder;
        var convertedPath = tempFolder.path + "/" + imageFile.name + ".tvg";
        var convertProcess = new $.oProcess(utransformBin, [
            "-outformat", "TVG", "-debug",
            "-resolution", imgInfo.width, imgInfo.height,
            "-outfile", convertedPath, imageFile.path
        ]);
        convertProcess.execute();

        var convertedFile = new $.oFile(convertedPath);
        if (convertedFile.exists) {
            drawing = element.addDrawing(1, 1, convertedPath, false);
        }
    }
    if (!drawing) {
        drawing = element.addDrawing(1, 1, imageFile.path, false);
    }

    var newImageNode = $.scn.root.addDrawingNode(
        layerName, new $.oPoint(0, 0, 0), element
    );
    newImageNode.alignment_rule = "ASIS";
    newImageNode.attributes.drawing.element.setValue(drawing.name, 1);
    newImageNode.attributes.drawing.element.column.extendExposures();

    var sceneResY = $.scene.resolutionY;
    if (imgInfo && imgInfo.height > 0 && sceneResY > 0) {
        var uniformScale = imgInfo.height / sceneResY;
        newImageNode.scale.x = uniformScale;
        newImageNode.scale.y = uniformScale;
    }

    node.getAttr(newImageNode.path, 1, "lineArtDrawingMode").setValue("BitmapDrawingMode");
    node.getAttr(newImageNode.path, 1, "applyMatteToColor").setValue(1); // 1 = Straight
    newImageNode.use_drawing_pivot = "Apply Embedded Pivot on Drawing Layer";

    AyonHarmony.substituteNode(oldNodePath, newImageNode.path);
    return oldNodePath;
}
replace_image
"""


class BitmapDrawingLoader(load.LoaderPlugin):
    """Import a single image as a Toon Boom bitmap drawing."""

    label = "Import bitmap drawing"
    product_base_types = {"image", "render", "review", "plate"}
    product_types = product_base_types
    representations = {"*"}
    extensions = {"png", "jpg", "jpeg", "tga", "sgi", "psd"}

    def load(self, context, name=None, namespace=None, data=None):
        """Plugin entry point.

        Args:
            context (:class:`pyblish.api.Context`): Context.
            name (str, optional): Container name.
            namespace (str, optional): Container namespace.
            data (dict, optional): Additional data passed into loader.

        """
        filepath = self.filepath_from_context(context).replace("\\", "/")
        product_name = context["product"]["name"]
        layer_name = self._container_name(context)

        read_node = harmony.send(
            {
                "function": import_image,
                "args": [filepath, layer_name],
            }
        )["result"]

        return harmony.containerise(
            product_name,
            namespace,
            read_node,
            context,
            self.__class__.__name__,
            nodes=[read_node],
        )

    def _container_name(self, context):
        """Build the same "{project}_{folder}_{product}_v{version}"
        naming AYON uses elsewhere in this addon (see
        ImageSequenceLoader), instead of the raw file basename or the
        bare product name.

        Args:
            container (dict): Container data.
        """
        project_name = context["project"]["name"]
        folder_name = context["folder"]["name"]
        product_name = context["product"]["name"]
        version = context["version"]["version"]
        return f"{project_name}_{folder_name}_{product_name}_v{version:03d}"

    def update(self, container, context):
        """Update loaded containers.

        Args:
            container (dict): Container data.
            context (dict): Representation context data.

        """
        filepath = self.filepath_from_context(context).replace("\\", "/")

        old_node = container["nodes"][0]
        layer_name = self._container_name(context)

        new_node = harmony.send(
            {
                "function": replace_image,
                "args": [filepath, old_node, layer_name],
            }
        )["result"]

        harmony.containerise(
            container["name"],
            container.get("namespace"),
            new_node,
            context,
            container.get("loader"),
            nodes=[new_node],
        )

    def remove(self, container):
        """Remove loaded container.

        Args:
            container (dict): Container data.

        """
        func = """function deleteNode(_node)
        {
            node.deleteNode(_node, true, true);
        }
        deleteNode
        """
        for node_path in container.get("nodes"):
            harmony.send({"function": func, "args": [node_path]})
            harmony.imprint(node_path, {}, remove=True)

    def switch(self, container, context):
        """Switch loaded representations."""
        self.update(container, context)
