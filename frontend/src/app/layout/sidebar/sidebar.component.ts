import { Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { IsActiveMatchOptions, NavigationEnd, PRIMARY_OUTLET, Router, RouterLink, RouterLinkActive } from '@angular/router';
import { filter, map, startWith } from 'rxjs';
import { NAVIGATION_ITEMS } from '../navigation/navigation.config';
import { IconComponent } from '../../shared/ui/icon/icon.component';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, IconComponent],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss'
})
export class SidebarComponent {
  private readonly router = inject(Router);
  readonly isNotFound = toSignal(this.router.events.pipe(
    filter((event) => event instanceof NavigationEnd),
    startWith(null),
    map(() => {
      let route = this.router.routerState.snapshot.root;
      let child;
      while ((child = route.children.find((candidate) => candidate.outlet === PRIMARY_OUTLET))) route = child;
      return route.data['isNotFound'] === true;
    })
  ), { requireSync: true });
  readonly items = NAVIGATION_ITEMS;
  readonly exactMatch: IsActiveMatchOptions = {
    paths: 'exact', queryParams: 'ignored', matrixParams: 'ignored', fragment: 'ignored'
  };
  readonly sectionMatch: IsActiveMatchOptions = { ...this.exactMatch, paths: 'subset' };
}
