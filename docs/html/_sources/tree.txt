Tree
====

Tree widget renders a hierarchical tree where child nodes can be queried on demand. It can be useful to show
folder like structures, hierarchical menus etc.

Tree & TreeNode Classes
-----------------------

.. class:: Tree(parent, width, do_animate)

   Creates a new tree widget in the `parent`.
   if `do_animate` is set, it will animate the expansion and closing of the tree
   
   .. attribute:: nodes
   
      dictionary of root nodes
      
   .. attribute:: allnodes
   
      dictionary of all nodes in the tree
      
   .. method:: addNode(parent, id, imagesrc, onclick, onexpand, opts, label)
   
      create a new TreeNode
      
      * `parent` - parent TreeNode which the node is to be created. `null` for root node
      * `id` - label (if not separately specified) of the new node
      * `imagesrc` - icon of the node
      * `onclick` - event to be called when node is clicked (selected)
      * `onexpand` - event to ba called when node is expanded
      * `opts` - node style options
      * `label` - if label is separate from id
      
   .. method:: collapse_all()
   
      Collapse all nodes
      
.. class:: TreeNode(tree, parent, id, imagesrc, onclick, onexpand, opts, label)

   This class is instantiated by :meth:`Tree.addNode`

   .. attribute:: parent 
   
      Parent node or the Tree (in case of root node)
      
   .. attribute:: nodes
   
      Dictionary of child nodes by id
      
   .. attribute:: opts
   
      Style of the node. Default `opts` is::
      
         opts = {
            show_exp_img:1
            ,show_icon:1
            ,label_style:{padding:'2px', cursor: 'pointer', fontSize:'11px'}
            ,onselect_style:{fontWeight: 'bold'}
            ,ondeselect_style:{fontWeight: 'normal'}
         }
   
   .. method:: select()
   
      Select the node
      
   .. method:: deselect()
   
      Deselect the node
      
   .. method:: show_selected()
   
      Show the style as selected
      
   .. method:: setlabel(t)
   
      Set the label of the node
      
   .. method:: setcolor(c)
   
      Set background color of the node
      
   .. method:: clear_child_nodes()
   
      Remove all child nodes

Example
-------

Example showing a tree in which the child nodes are queried from the server `onexpand`::

   // Tree
   // ----------

   pscript.load_cat_tree = function(){
   //create category tree
     if(!pscript.cat_tree){
       pscript.make_cat_tree();
     }
     pscript.get_parent_category();
   }

   pscript.get_parent_category = function(){
     if (pscript.cat_tree){
       pscript.cat_tree.innerHTML = '';
     }
     var callback1 = function(r,rt){
       cl = r.message;
       var has_children = true; var imgsrc = 'images/icons/page.gif';
       for(i=0; i<cl.length;i++){
         var n = pscript.cat_tree.addNode(null, cl[i][1],imgsrc, pscript.cat_tree.std_onclick, has_children ? pscript.cat_tree.std_onexp : null, null, cl[i][0]);
         n.rec = cl[i]; n.rec.name = cl[i][0]; n.rec.label = cl[i][1];
         n.rec.parent_category = '';
       }
     }
     $c_obj('Ticket Control','get_root_category','',callback1);
   }

   pscript.make_cat_tree = function() {
      var tree = new Tree(pscript.faq_cat_tree, '100%');
      pscript.cat_tree = tree;

      // on click
      pscript.cat_tree.std_onclick = function(node) {
         pscript.cur_node = node;
         pscript.cur_node_val = node.rec.name;
         //make faq list
           pscript.make_faq_lst('frm_node');
      }

      // on expand
      pscript.cat_tree.std_onexp = function(node) {

         if(node.expanded_once)return;
         $ds(node.loading_div);
      
         var callback = function(r,rt) {
            $dh(node.loading_div);
            var n = pscript.cat_tree.allnodes[r.message.parent_category];
            var cl = r.message.category;

            for(var i=0;i<cl.length;i++) {
               var imgsrc='images/icons/page.gif';
               var has_children = true;
               var t = pscript.cat_tree.addNode(n, cl[i].name, imgsrc, pscript.cat_tree.std_onclick, has_children ? pscript.cat_tree.std_onexp : null, null, cl[i].category_name);
               t.rec = cl[i];
               t.rec.name = cl[i].name;
               t.rec.label = cl[i].category_name;
               t.parent_category = r.message.parent_category; //alert(t)
            }
         }
         var arg = {}
         arg['category'] = node.rec.name;
         $c_obj('Ticket Control','get_categories',docstring(arg),callback);
      }
   }
   
   