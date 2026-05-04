import os

def setup_healthgate_assets():
    # 1. CrÃ©ation des dossiers
    directories = [
        "assets",
        "app/utils",
        "app/components",
        "app/pages"
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"âœ… Dossier crÃ©Ã© : {directory}")

    # 2. Instructions pour les images
    images_to_create = [
        "assets/logo_ecc.png",       
        "assets/hopital_afrique.jpg", 
        "assets/favicon.ico"         
    ]

    for img_path in images_to_create:
        if not os.path.exists(img_path):
            with open(img_path, 'wb') as f:
                pass 
            print(f"ðŸ“¸ Emplacement rÃ©servÃ© crÃ©Ã© : {img_path}")
            print(f"   ðŸ‘‰ Pense Ã  remplacer {img_path} par ta vraie image.")

if __name__ == "__main__":
    setup_healthgate_assets()
    print("\nðŸš€ Structure HealthGate prÃªte pour le design !")