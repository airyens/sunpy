============
Installation
============

Below are instructions for installation SunPy and its prerequisites on 
different platforms.

Installing Prerequisites
------------------------
For instructions on installing these prereqs on your system, choose your OS from
the list below.

.. toctree::
   :maxdepth: 1
   
   mac
   linux
   win
   
Installing SunPy
----------------
Once you have successfully installed Python and the prereqs as described in the
sections above you are ready to install SunPy itself. There are several 
different methods for installing SunPy. In general, unless you require a more
recent version or plan to contribute to the development of SunPy, it is 
recommended that you use one of the methods for installing the latest stable
version of SunPy.

.. toctree::
   :maxdepth: 1
   
   stable
   git
   
Testing your installation
-------------------------

Now you can test your installation. Open a new Python shell and type these 
commands: ::

>>> import sunpy
>>> sunpy.make_map(sunpy.AIA_171_IMAGE).show()

If all goes well you should see an AIA 171 image on your screen.
