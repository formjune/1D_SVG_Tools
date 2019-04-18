- 1D_ SVG_Tools
is an addon for Blender 2.79, a toolkit that provides tools for SVG files.
It allow to split/merge given SVG files, find (parse)/copy images listed in it and slice specially prepared
files to multiple icons.
Main topic for IconSlicer tool:
https://forum.freecadweb.org/viewtopic.php?f=34&t=
- INSTALLATION
    - Get Blender 2.79 from blender.org
    - Open program, open prefrences window (File – User Prefrences, or Ctrl+Alt+U shortcut).
    - In addons section press install addon from file button, specify 1D_SVG_Tools.py file,
       confirm, enable addon’s checkbox and press Save User Prefrences button.
    - Addon can be found in T-panel – 1D tab – 1D SVG Tools.

Addons instalation:
![Set_Linear_Demo](https://raw.githubusercontent.com/formjune/1D_SVG_Tools/master/docs/1.png)


## - SVG TOOLS

SVG input split - splits svg file into pieces not exceeding selected size.

**>Controls:
Input** - SVG file of directory with SVG files to proceed.
**Output** - directory or empty for input directory.
**Max Size** - size for output files

SVG output merge - merge files into one. Output file will be named MERGE.SVG

**>Controls:
Input** - directory with SVG files to proceed.
**Output** - directory or empty for input directory.


SVG parse images
Scans SVG file for external image links and creates/rewrites Blneder interlnal text file called "svg
parse images.txt" with found paths.

**>Controls:
Input** - SVG file to scan.
**Crop Absolute Names** - Convert absolute paths into "input directory + file name". Result for absolute names will
be written into separated data block. Used for finding files near SVG (integrity check for archiving).

SVG Parse Images result:
![Set_Linear_Demo](https://raw.githubusercontent.com/formjune/1D_SVG_Tools/master/docs/2.png)

SVG copy images - Copy all files from external links found by SVG parse images into one
directory.

**>Controls:
Input** - svg file to scan
**Output** - directory or empty for input directory.

SVG icon slicer (Slice Transformed checkbox = OFF) - slices single SVG file with icons into
multiple SVG icon files.


SVG Icon Slicer operation principle:
![Set_Linear_Demo](https://raw.githubusercontent.com/formjune/1D_SVG_Tools/master/docs/3.png)

Icon filenames are taken from link of image objects from right side to the icon block.
Grids, Metadata and License data are copied from original SVG.
Objects with transformation matrices aren't supported properly, use Slice Transformed checkbox to
detect them. Text blocks are ignored.

**>Controls:
Input** - file to slice
**Output** - directory or empty for input directory. In case of leaving empty files will be written in new directory
named "input file + output_name"

SVG icon slicer (Slice Transformed checkbox = ON) — an SVG analysis tool.
Creates temporal copy of SVG file, with all objects that have transformations moved to
"TranMatrix" layer, as they cause problems with SVG icon slicing. Used for detecting objects with
transformations and then fixing them in the original file.

**>Controls:
Input** - file to analyze
**Output** - directory or empty for input directory. In case of leaving empty name will be "input file + _out.svg"
