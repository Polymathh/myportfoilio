from django.urls import path
from . import views

urlpatterns = [
    path('admin/', views.custom_admin_dashboard, name='custom_admin_dashboard'),
    path('admin/login/', views.custom_admin_login, name='custom_admin_login'),
    path('admin/logout/', views.custom_admin_logout, name='custom_admin_logout'),
    path('admin/profile/', views.custom_admin_profile, name='custom_admin_profile'),
    path('admin/seo/', views.custom_admin_seo, name='custom_admin_seo'),
    path('admin/projects/', views.custom_admin_projects, name='custom_admin_projects'),
    path('admin/projects/add/', views.custom_admin_project_edit, name='custom_admin_project_add'),
    path('admin/projects/<int:pk>/move/<str:direction>/', views.custom_admin_project_move, name='custom_admin_project_move'),
    path('admin/projects/<int:pk>/delete/', views.custom_admin_project_delete, name='custom_admin_project_delete'),
    path('admin/projects/<int:pk>/', views.custom_admin_project_edit, name='custom_admin_project_edit'),
    path('admin/posts/', views.custom_admin_posts, name='custom_admin_posts'),
    path('admin/posts/add/', views.custom_admin_post_edit, name='custom_admin_post_add'),
    path('admin/posts/<int:pk>/move/<str:direction>/', views.custom_admin_post_move, name='custom_admin_post_move'),
    path('admin/posts/<int:pk>/delete/', views.custom_admin_post_delete, name='custom_admin_post_delete'),
    path('admin/posts/<int:pk>/', views.custom_admin_post_edit, name='custom_admin_post_edit'),
    path('admin/contacts/', views.custom_admin_contacts, name='custom_admin_contacts'),
    path('', views.home, name='home'),
    path('blog/', views.blog_list, name='blog_list'),
    path('blog/<slug:slug>/', views.blog_detail, name='blog_detail'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('sitemap.xml', views.sitemap_xml, name='sitemap_xml'),
]

